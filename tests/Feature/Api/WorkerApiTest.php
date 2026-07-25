<?php

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;
use Illuminate\Contracts\Bus\Dispatcher;
use Illuminate\Contracts\Bus\QueueingDispatcher;
use Illuminate\Http\Testing\File as UploadedTestFile;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

beforeEach(function () {
    config()->set('services.worker.token', 'test-worker-token');
    config()->set('services.worker.throttle_per_minute', 1_000);
    Storage::fake('public');
});

function workerHeaders(): array
{
    return [
        'Authorization' => 'Bearer test-worker-token',
        'Accept' => 'application/json',
    ];
}

function workerMeetingPayload(array $overrides = []): array
{
    return array_merge([
        'worker_item_id' => (string) Str::uuid(),
        'client_id' => Client::factory()->create()->id,
        'title' => 'Worker meeting',
        'meeting_at' => '2026-07-10T13:03:47+03:00',
        'duration_seconds' => 3777,
        'start_transcript_server' => false,
    ], $overrides);
}

function createWorkerMeeting($test, array $overrides = []): Meeting
{
    $payload = workerMeetingPayload($overrides);
    $response = $test->postJson('/api/v1/worker/meetings', $payload, workerHeaders());
    $response->assertCreated();

    return Meeting::query()->findOrFail($response->json('data.id'));
}

function workerTranscript(array $segments): string
{
    return json_encode([
        'driver' => 'worker',
        'model' => 'large-v3',
        'language' => 'ro',
        'language_probability' => 0.99,
        'duration' => 10,
        'runtime' => (object) ['device' => 'rocm'],
        'segments' => $segments,
    ], JSON_THROW_ON_ERROR);
}

function monoPcmWave(string $samples = "\0\0\0\0"): string
{
    $dataSize = strlen($samples);

    return 'RIFF'
        .pack('V', 36 + $dataSize)
        .'WAVEfmt '
        .pack('VvvVVvv', 16, 1, 1, 16_000, 32_000, 2, 16)
        .'data'
        .pack('V', $dataSize)
        .$samples;
}

it('requires a configured constant-time bearer credential', function () {
    config()->set('services.worker.token', null);
    $this->getJson('/api/v1/worker/clients', workerHeaders())
        ->assertStatus(503)
        ->assertExactJson([
            'error' => [
                'code' => 'worker_auth_unavailable',
                'message' => 'Worker authentication is not configured.',
            ],
        ]);

    config()->set('services.worker.token', 'test-worker-token');

    $this->getJson('/api/v1/worker/clients')
        ->assertUnauthorized()
        ->assertJsonPath('error.code', 'unauthenticated');

    $this->getJson('/api/v1/worker/clients', [
        'Authorization' => 'Bearer wrong-token',
    ])->assertUnauthorized()
        ->assertJsonMissing(['test-worker-token'])
        ->assertJsonMissing(['wrong-token']);
});

it('returns an ordered minimal client list', function () {
    Client::factory()->create(['name' => 'Zulu']);
    Client::factory()->create(['name' => 'Alpha']);

    $this->getJson('/api/v1/worker/clients', workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.0.name', 'Alpha')
        ->assertJsonPath('data.1.name', 'Zulu')
        ->assertJsonMissingPath('data.0.email');
});

it('creates metadata-only meetings and replays identical metadata idempotently', function () {
    $payload = workerMeetingPayload();

    $first = $this->postJson('/api/v1/worker/meetings', $payload, workerHeaders());
    $first->assertCreated()
        ->assertJsonPath('data.worker_item_id', $payload['worker_item_id'])
        ->assertJsonPath('data.start_transcript_server', false)
        ->assertJsonPath('data.meeting_at', '2026-07-10T10:03:47+00:00');

    $second = $this->postJson('/api/v1/worker/meetings', $payload, workerHeaders());
    $second->assertOk()
        ->assertJsonPath('data.id', $first->json('data.id'));

    $meeting = Meeting::query()->findOrFail($first->json('data.id'));
    expect($meeting->video_path)->toBeNull()
        ->and($meeting->workerIngestion)->not->toBeNull()
        ->and(Meeting::query()->count())->toBe(1);
});

it('rejects conflicting canonical metadata for a replayed worker item', function () {
    $payload = workerMeetingPayload();
    $this->postJson('/api/v1/worker/meetings', $payload, workerHeaders())->assertCreated();

    $this->postJson('/api/v1/worker/meetings', [
        ...$payload,
        'title' => 'Changed title',
    ], workerHeaders())
        ->assertConflict()
        ->assertJsonPath('error.code', 'meeting_metadata_conflict');

    expect(Meeting::query()->count())->toBe(1);
});

it('validates UUID v4 metadata and offset-bearing calendar datetimes', function () {
    $payload = workerMeetingPayload([
        'worker_item_id' => '00000000-0000-1000-8000-000000000000',
        'meeting_at' => '2026-02-30T13:03:47+03:00',
    ]);

    $this->postJson('/api/v1/worker/meetings', $payload, workerHeaders())
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'validation_failed')
        ->assertJsonStructure([
            'error' => [
                'details' => ['worker_item_id', 'meeting_at'],
            ],
        ]);

    expect(Meeting::query()->count())->toBe(0);
});

it('reconciles durable meeting and artifact state', function () {
    $meeting = createWorkerMeeting($this);

    $this->getJson("/api/v1/worker/meetings/{$meeting->id}", workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.id', $meeting->id)
        ->assertJsonPath('data.artifacts.video.uploaded', false)
        ->assertJsonPath('data.artifacts.audio.uploaded', false)
        ->assertJsonPath('data.artifacts.transcript.uploaded', false);

    $ordinaryMeeting = Meeting::factory()->create();
    $this->getJson("/api/v1/worker/meetings/{$ordinaryMeeting->id}", workerHeaders())
        ->assertNotFound()
        ->assertJsonPath('error.code', 'not_found');
});

it('stores video at a server-selected fixed path and handles retries, conflicts, and replacement', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/video";

    $first = UploadedTestFile::fake()
        ->createWithContent('../../untrusted-name.mp4', 'first-video')
        ->mimeType('video/mp4');
    $this->post($url, ['file' => $first], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'uploaded');

    $path = "meetings/{$meeting->client_id}/{$meeting->id}/video.mp4";
    Storage::disk('public')->assertExists($path);
    expect($meeting->fresh()->video_path)->toBe($path)
        ->and(Storage::disk('public')->files("meetings/{$meeting->client_id}/{$meeting->id}"))
        ->toBe([$path]);

    $retry = UploadedTestFile::fake()
        ->createWithContent('renamed.mp4', 'first-video')
        ->mimeType('video/mp4');
    $this->post($url, ['file' => $retry], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'already_uploaded');

    $conflict = UploadedTestFile::fake()
        ->createWithContent('other.mp4', 'second-video')
        ->mimeType('video/mp4');
    $this->post($url, ['file' => $conflict], workerHeaders())
        ->assertConflict()
        ->assertJsonPath('error.code', 'artifact_hash_conflict');
    expect(Storage::disk('public')->get($path))->toBe('first-video');

    $replacement = UploadedTestFile::fake()
        ->createWithContent('other.mov', 'second-video')
        ->mimeType('video/quicktime');
    $this->post($url, ['file' => $replacement, 'replace' => 'true'], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'uploaded');

    Storage::disk('public')->assertMissing($path);
    Storage::disk('public')->assertExists("meetings/{$meeting->client_id}/{$meeting->id}/video.mov");
});

it('never dispatches server transcription when the persisted flag is false', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this, ['start_transcript_server' => false]);
    $file = UploadedTestFile::fake()->createWithContent('video.mp4', 'video')->mimeType('video/mp4');

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => $file],
        workerHeaders(),
    )->assertOk();

    Bus::assertNotDispatched(TranscribeMeetingJob::class);
    expect($meeting->workerIngestion->fresh()->server_transcription_dispatched_at)->toBeNull();
});

it('dispatches server transcription exactly once after a true-flag video upload', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this, ['start_transcript_server' => true]);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/video";

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('video.mp4', 'video')->mimeType('video/mp4'),
    ], workerHeaders())->assertOk();
    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('again.mp4', 'video')->mimeType('video/mp4'),
    ], workerHeaders())->assertOk()->assertJsonPath('data.state', 'already_uploaded');

    Bus::assertDispatchedTimes(TranscribeMeetingJob::class, 1);
    expect($meeting->workerIngestion->fresh()->server_transcription_dispatched_at)->not->toBeNull();
});

it('does not record dispatch success when queue dispatch fails and retries later', function () {
    $meeting = createWorkerMeeting($this, ['start_transcript_server' => true]);
    $dispatcher = Mockery::mock(QueueingDispatcher::class);
    $dispatcher->shouldReceive('dispatch')->once()->andThrow(new RuntimeException('queue unavailable'));
    app()->instance(Dispatcher::class, $dispatcher);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/video";

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('video.mp4', 'video')->mimeType('video/mp4'),
    ], workerHeaders())
        ->assertStatus(500)
        ->assertJsonPath('error.code', 'server_error');

    expect($meeting->workerIngestion->fresh()->server_transcription_dispatched_at)->toBeNull()
        ->and($meeting->workerIngestion->fresh()->video_sha256)->not->toBeNull();

    $retryDispatcher = Mockery::mock(QueueingDispatcher::class);
    $retryDispatcher->shouldReceive('dispatch')->once()->andReturnNull();
    app()->instance(Dispatcher::class, $retryDispatcher);
    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('retry.mp4', 'video')->mimeType('video/mp4'),
    ], workerHeaders())->assertOk()->assertJsonPath('data.state', 'already_uploaded');

    expect($meeting->workerIngestion->fresh()->server_transcription_dispatched_at)->not->toBeNull();
});

it('validates and independently retries mono PCM audio artifacts', function () {
    $meeting = createWorkerMeeting($this);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/audio";
    $wave = monoPcmWave();

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('renamed.wav', $wave)->mimeType('audio/wav'),
    ], workerHeaders())->assertOk()->assertJsonPath('data.state', 'uploaded');

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('again.wav', $wave)->mimeType('audio/wav'),
    ], workerHeaders())->assertOk()->assertJsonPath('data.state', 'already_uploaded');

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('bad.wav', 'not-wave')->mimeType('audio/wav'),
        'replace' => true,
    ], workerHeaders())
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'invalid_audio');
});

it('imports transcript replacements atomically, completes the meeting, and preserves known-good state on invalid input', function () {
    $meeting = createWorkerMeeting($this);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/transcript";
    $valid = workerTranscript([
        ['speaker' => 'A', 'text' => 'known good', 'start' => 0, 'end' => 2],
    ]);

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('anything.json', $valid)->mimeType('application/json'),
    ], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'uploaded')
        ->assertJsonPath('data.segments', 1);

    $path = "meetings/{$meeting->client_id}/{$meeting->id}/transcript.json";
    $knownGoodFile = Storage::disk('public')->get($path);
    $knownGoodHash = $meeting->workerIngestion->fresh()->transcript_sha256;
    expect($meeting->fresh()->status)->toBe('completed')
        ->and($meeting->transcriptions()->first()->text)->toBe('known good');

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('bad.json', '{broken')->mimeType('application/json'),
        'replace' => true,
    ], workerHeaders())
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'invalid_transcript');

    expect(Storage::disk('public')->get($path))->toBe($knownGoodFile)
        ->and($meeting->transcriptions()->first()->text)->toBe('known good')
        ->and($meeting->workerIngestion->fresh()->transcript_sha256)->toBe($knownGoodHash);
});

it('applies transcript hash conflict and explicit replacement semantics', function () {
    $meeting = createWorkerMeeting($this);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/transcript";
    $first = workerTranscript([
        ['speaker' => 'A', 'text' => 'first', 'start' => 0, 'end' => 1],
    ]);
    $second = workerTranscript([
        ['speaker' => 'B', 'text' => 'second', 'start' => 1, 'end' => 2],
    ]);

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('one.json', $first)->mimeType('application/json'),
    ], workerHeaders())->assertOk();
    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('two.json', $second)->mimeType('application/json'),
    ], workerHeaders())->assertConflict();
    expect(Transcription::query()->where('meeting_id', $meeting->id)->value('text'))->toBe('first');

    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('two.json', $second)->mimeType('application/json'),
        'replace' => true,
    ], workerHeaders())->assertOk();
    expect(Transcription::query()->where('meeting_id', $meeting->id)->value('text'))->toBe('second');
});

it('enforces configured upload limits and the named API throttle', function () {
    $meeting = createWorkerMeeting($this);
    config()->set('services.worker.artifacts.video.max_bytes', 3);

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => UploadedTestFile::fake()->createWithContent('video.mp4', 'four')->mimeType('video/mp4')],
        workerHeaders(),
    )->assertUnprocessable()->assertJsonPath('error.code', 'validation_failed');

    config()->set('services.worker.throttle_per_minute', 1);
    $server = ['REMOTE_ADDR' => '10.20.30.40'];
    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', workerHeaders())->assertOk();
    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', workerHeaders())
        ->assertTooManyRequests()
        ->assertJsonPath('error.code', 'rate_limit_exceeded');
});
