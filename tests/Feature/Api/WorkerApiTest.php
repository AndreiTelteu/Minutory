<?php

use App\Exceptions\WorkerApiException;
use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;
use App\Models\WorkerIngestion;
use App\Services\AtomicFilesystem;
use App\Services\VideoProbe;
use Illuminate\Contracts\Bus\Dispatcher;
use Illuminate\Contracts\Bus\QueueingDispatcher;
use Illuminate\Http\Testing\File as UploadedTestFile;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

beforeEach(function () {
    config()->set('services.worker.token', 'test-worker-token');
    config()->set('services.worker.auth_attempts_per_minute', 1_000);
    config()->set('services.worker.auth_attempts_per_credential_per_minute', 1_000);
    config()->set('services.worker.throttle_per_minute', 1_000);
    config()->set('queue.default', 'database');
    config()->set('queue.connections.database.connection', null);
    Storage::fake('public');

    $probe = Mockery::mock(VideoProbe::class);
    $probe->shouldReceive('validate')->byDefault()->andReturnNull();
    app()->instance(VideoProbe::class, $probe);
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
        'language' => 'ro',
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

function workerVideo(string $name = 'video.mp4', string $marker = 'video'): UploadedTestFile
{
    $extension = strtolower(pathinfo($name, PATHINFO_EXTENSION));
    $brand = $extension === 'mov' ? 'qt  ' : 'mp42';
    $content = pack('N', 24).'ftyp'.$brand.pack('N', 0).$marker;

    return UploadedTestFile::fake()->createWithContent(
        $name,
        $content,
        $extension === 'mov' ? 'video/quicktime' : 'video/mp4',
    );
}

class WorkerApiMutationOnEnsureFilesystem extends AtomicFilesystem
{
    private bool $mutated = false;

    public function __construct(private readonly Closure $mutation) {}

    public function ensureDirectory(string $path): void
    {
        parent::ensureDirectory($path);

        if (! $this->mutated) {
            $this->mutated = true;
            ($this->mutation)();
        }
    }
}

class WorkerApiRestoreFailingFilesystem extends AtomicFilesystem
{
    public function move(string $from, string $to): bool
    {
        if (str_contains($from, '.backup.') && ! str_contains($to, '.backup.')) {
            return false;
        }

        return parent::move($from, $to);
    }
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
        ->assertJsonPath('data.language', 'ro')
        ->assertJsonPath('data.meeting_at', '2026-07-10T10:03:47+00:00');

    $second = $this->postJson('/api/v1/worker/meetings', $payload, workerHeaders());
    $second->assertOk()
        ->assertJsonPath('data.id', $first->json('data.id'));

    $meeting = Meeting::query()->findOrFail($first->json('data.id'));
    expect($meeting->video_path)->toBeNull()
        ->and($meeting->language)->toBe('ro')
        ->and($meeting->workerIngestion)->not->toBeNull()
        ->and(Meeting::query()->count())->toBe(1);
});

it('stores the requested worker meeting language and rejects unsupported values', function () {
    $response = $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'language' => 'en',
    ]), workerHeaders());

    $response->assertCreated()
        ->assertJsonPath('data.language', 'en');

    expect(Meeting::query()->findOrFail($response->json('data.id'))->language)->toBe('en');

    $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'language' => 'fr',
    ]), workerHeaders())
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'validation_failed')
        ->assertJsonStructure(['error' => ['details' => ['language']]]);
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

it('canonicalizes uppercase worker UUIDs for lowercase replay', function () {
    $uppercase = strtoupper((string) Str::uuid());
    $payload = workerMeetingPayload(['worker_item_id' => $uppercase]);

    $first = $this->postJson('/api/v1/worker/meetings', $payload, workerHeaders());
    $first->assertCreated();

    $this->postJson('/api/v1/worker/meetings', [
        ...$payload,
        'worker_item_id' => strtolower($uppercase),
    ], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.id', $first->json('data.id'))
        ->assertJsonPath('data.worker_item_id', strtolower($uppercase));

    expect(Meeting::query()->count())->toBe(1);
});

it('rejects true server transcription unless the queue is transactional database-backed', function () {
    config()->set('queue.default', 'redis');

    $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'start_transcript_server' => true,
    ]), workerHeaders())
        ->assertStatus(503)
        ->assertJsonPath('error.code', 'unsupported_server_transcription_queue');
    expect(Meeting::query()->count())->toBe(0);

    $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'start_transcript_server' => false,
    ]), workerHeaders())->assertCreated();

    config()->set('queue.default', 'database');
    config()->set('queue.connections.database.connection', 'different-connection');
    $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'start_transcript_server' => true,
    ]), workerHeaders())
        ->assertStatus(503)
        ->assertJsonPath('error.code', 'unsupported_server_transcription_queue');

    config()->set('queue.connections.database.connection', null);
    config()->set('queue.connections.database.after_commit', true);
    $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'start_transcript_server' => true,
    ]), workerHeaders())
        ->assertStatus(503)
        ->assertJsonPath('error.code', 'unsupported_server_transcription_queue');
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

it('stores pre-1970 and post-2038 meeting datetimes as UTC datetimes', function (string $meetingAt, string $expectedUtc) {
    $response = $this->postJson('/api/v1/worker/meetings', workerMeetingPayload([
        'meeting_at' => $meetingAt,
    ]), workerHeaders());

    $response->assertCreated()
        ->assertJsonPath('data.meeting_at', $expectedUtc);

    expect(Meeting::query()->findOrFail($response->json('data.id'))->meeting_at?->utc()->toIso8601String())
        ->toBe($expectedUtc);
})->with([
    ['1960-01-02T03:04:05+02:00', '1960-01-02T01:04:05+00:00'],
    ['2050-12-31T23:59:59-05:00', '2051-01-01T04:59:59+00:00'],
]);

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

    $first = workerVideo('../../untrusted-name.mp4', 'first-video');
    $this->post($url, ['file' => $first], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'uploaded');

    $path = "meetings/{$meeting->client_id}/{$meeting->id}/video.mp4";
    Storage::disk('public')->assertExists($path);
    expect($meeting->fresh()->video_path)->toBe($path)
        ->and(Storage::disk('public')->files("meetings/{$meeting->client_id}/{$meeting->id}"))
        ->toBe([$path]);

    $retry = workerVideo('renamed.mp4', 'first-video');
    $this->post($url, ['file' => $retry], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'already_uploaded');

    $conflict = workerVideo('other.mp4', 'second-video');
    $this->post($url, ['file' => $conflict], workerHeaders())
        ->assertConflict()
        ->assertJsonPath('error.code', 'artifact_hash_conflict');
    expect(Storage::disk('public')->get($path))->toBe(workerVideo('copy.mp4', 'first-video')->getContent());

    $replacement = workerVideo('other.mov', 'second-video');
    $this->post($url, ['file' => $replacement, 'replace' => 'true'], workerHeaders())
        ->assertOk()
        ->assertJsonPath('data.state', 'uploaded');

    Storage::disk('public')->assertMissing($path);
    Storage::disk('public')->assertExists("meetings/{$meeting->client_id}/{$meeting->id}/video.mov");
});

it('restores MP4 metadata and files when an extension-changing replacement fails after the swap', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/video";

    $this->post($url, ['file' => workerVideo('original.mp4', 'original')], workerHeaders())->assertOk();

    $oldIngestion = $meeting->workerIngestion->fresh();
    $oldPath = $meeting->fresh()->video_path;
    $oldContents = Storage::disk('public')->get($oldPath);

    Meeting::updated(function (Meeting $updated): void {
        if (str_ends_with((string) $updated->video_path, '/video.mov')) {
            throw new RuntimeException('injected meeting update failure');
        }
    });

    $response = $this->post($url, [
        'file' => workerVideo('replacement.mov', 'replacement'),
        'replace' => true,
    ], workerHeaders());

    $response->assertStatus(500)
        ->assertJsonPath('error.code', 'server_error');
    expect($response->getContent())->not->toContain($oldPath);

    $freshIngestion = $meeting->workerIngestion->fresh();
    expect($meeting->fresh()->video_path)->toBe($oldPath)
        ->and($freshIngestion->video_sha256)->toBe($oldIngestion->video_sha256)
        ->and($freshIngestion->video_bytes)->toBe($oldIngestion->video_bytes)
        ->and($freshIngestion->video_uploaded_at?->toISOString())
        ->toBe($oldIngestion->video_uploaded_at?->toISOString())
        ->and(Storage::disk('public')->get($oldPath))->toBe($oldContents);
    Storage::disk('public')->assertMissing("meetings/{$meeting->client_id}/{$meeting->id}/video.mov");
});

it('retains and critically logs the only video backup when restoration fails', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/video";
    $this->post($url, ['file' => workerVideo('original.mp4', 'original')], workerHeaders())->assertOk();

    app()->instance(AtomicFilesystem::class, new WorkerApiRestoreFailingFilesystem);
    Log::spy();
    WorkerIngestion::updated(function (WorkerIngestion $updated): void {
        if ($updated->wasChanged('video_sha256')) {
            throw new RuntimeException('injected rollback');
        }
    });

    $response = $this->post($url, [
        'file' => workerVideo('replacement.mp4', 'replacement'),
        'replace' => true,
    ], workerHeaders());

    $response->assertStatus(500)
        ->assertJsonPath('error.code', 'server_error')
        ->assertJsonMissing(['backup']);
    expect($response->getContent())->not->toContain(Storage::disk('public')->path(''));

    $directory = Storage::disk('public')->path("meetings/{$meeting->client_id}/{$meeting->id}");
    $backups = glob($directory.'/video.mp4.backup.*');
    expect($backups)->toHaveCount(1)
        ->and(file_get_contents($backups[0]))->toBe(workerVideo('copy.mp4', 'original')->getContent())
        ->and($meeting->fresh()->video_path)->toEndWith('/video.mp4');

    Log::shouldHaveReceived('critical')
        ->once()
        ->withArgs(fn (string $message, array $context): bool => $message === 'Artifact recovery requires manual intervention.'
            && $context['backup_path'] === $backups[0]);
});

it('uses the lock-time hash for video, audio, and transcript conflict decisions', function (string $artifact) {
    $meeting = createWorkerMeeting($this);
    $lockedHash = str_repeat('a', 64);

    app()->instance(AtomicFilesystem::class, new WorkerApiMutationOnEnsureFilesystem(
        function () use ($meeting, $artifact, $lockedHash): void {
            DB::table('worker_ingestions')
                ->where('meeting_id', $meeting->id)
                ->update([
                    "{$artifact}_sha256" => $lockedHash,
                    "{$artifact}_bytes" => 123,
                    "{$artifact}_uploaded_at" => now(),
                ]);
        }
    ));

    $file = match ($artifact) {
        'video' => workerVideo('stale.mp4', 'new'),
        'audio' => UploadedTestFile::fake()->createWithContent('stale.wav', monoPcmWave()),
        'transcript' => UploadedTestFile::fake()->createWithContent('stale.json', workerTranscript([
            ['speaker' => 'A', 'text' => 'new', 'start' => 0, 'end' => 1],
        ])),
    };

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/{$artifact}",
        ['file' => $file],
        workerHeaders(),
    )
        ->assertConflict()
        ->assertJsonPath('error.code', 'artifact_hash_conflict');

    expect($meeting->workerIngestion->fresh()->getAttribute("{$artifact}_sha256"))->toBe($lockedHash);
})->with(['video', 'audio', 'transcript']);

it('never dispatches server transcription when the persisted flag is false', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this, ['start_transcript_server' => false]);
    $file = workerVideo();

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => $file],
        workerHeaders(),
    )->assertOk();

    Bus::assertNotDispatched(TranscribeMeetingJob::class);
    expect($meeting->workerIngestion->fresh()->server_transcription_dispatched_at)->toBeNull();
});

it('rejects a true-flag video before storage if queue configuration becomes unsupported', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this, ['start_transcript_server' => true]);
    config()->set('queue.default', 'redis');

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => workerVideo()],
        workerHeaders(),
    )
        ->assertStatus(503)
        ->assertJsonPath('error.code', 'unsupported_server_transcription_queue');

    expect($meeting->workerIngestion->fresh()->video_sha256)->toBeNull()
        ->and($meeting->fresh()->video_path)->toBeNull();
    Bus::assertNothingDispatched();
});

it('dispatches server transcription exactly once after a true-flag video upload', function () {
    Bus::fake();
    $meeting = createWorkerMeeting($this, ['start_transcript_server' => true]);
    $url = "/api/v1/worker/meetings/{$meeting->id}/artifacts/video";

    $this->post($url, [
        'file' => workerVideo(),
    ], workerHeaders())->assertOk();
    $this->post($url, [
        'file' => workerVideo('again.mp4'),
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
        'file' => workerVideo(),
    ], workerHeaders())
        ->assertStatus(500)
        ->assertJsonPath('error.code', 'server_error');

    expect($meeting->workerIngestion->fresh()->server_transcription_dispatched_at)->toBeNull()
        ->and($meeting->workerIngestion->fresh()->video_sha256)->not->toBeNull();

    $retryDispatcher = Mockery::mock(QueueingDispatcher::class);
    $retryDispatcher->shouldReceive('dispatch')->once()->andReturnNull();
    app()->instance(Dispatcher::class, $retryDispatcher);
    $this->post($url, [
        'file' => workerVideo('retry.mp4'),
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

it('rejects corrupt video content without storing artifact state', function () {
    $meeting = createWorkerMeeting($this);
    $probe = Mockery::mock(VideoProbe::class);
    $probe->shouldReceive('validate')
        ->once()
        ->andThrow(new WorkerApiException('invalid_video', 'The uploaded file is not a readable video.', 422));
    app()->instance(VideoProbe::class, $probe);

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => workerVideo('corrupt.mp4', 'corrupt')],
        workerHeaders(),
    )
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'invalid_video');

    expect($meeting->workerIngestion->fresh()->video_sha256)->toBeNull()
        ->and($meeting->fresh()->video_path)->toBeNull();
});

it('rejects WAV files with empty, truncated, or internally inconsistent data', function (string $wave) {
    $meeting = createWorkerMeeting($this);

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/audio",
        ['file' => UploadedTestFile::fake()->createWithContent('corrupt.wav', $wave)],
        workerHeaders(),
    )
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'invalid_audio');

    expect($meeting->workerIngestion->fresh()->audio_sha256)->toBeNull();
})->with([
    'empty data chunk' => fn (): string => monoPcmWave(''),
    'truncated chunk' => fn (): string => substr(monoPcmWave(), 0, -1),
    'bad byte rate' => fn (): string => substr_replace(monoPcmWave(), pack('V', 123), 28, 4),
    'bad block align' => fn (): string => substr_replace(monoPcmWave(), pack('v', 4), 32, 2),
]);

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

    $overflow = workerTranscript([
        ['speaker' => 'A', 'text' => 'overflow', 'start' => 0, 'end' => 10_000_000],
    ]);
    $this->post($url, [
        'file' => UploadedTestFile::fake()->createWithContent('overflow.json', $overflow),
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

it('enforces configured upload limits and the authenticated API throttle', function () {
    $meeting = createWorkerMeeting($this);
    config()->set('services.worker.artifacts.video.max_bytes', 3);

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => workerVideo('video.mp4', 'four')],
        workerHeaders(),
    )->assertUnprocessable()->assertJsonPath('error.code', 'validation_failed');

    config()->set('services.worker.token', 'throttle-worker-token');
    config()->set('services.worker.throttle_per_minute', 1);
    $server = ['REMOTE_ADDR' => '10.20.30.40'];
    $headers = ['Authorization' => 'Bearer throttle-worker-token'];
    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', $headers)->assertOk();
    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', $headers)
        ->assertTooManyRequests()
        ->assertJsonPath('error.code', 'rate_limit_exceeded');
});

it('throttles invalid bearer attempts before authentication', function () {
    config()->set('services.worker.auth_attempts_per_minute', 2);
    config()->set('services.worker.auth_attempts_per_credential_per_minute', 2);
    $server = ['REMOTE_ADDR' => '10.99.0.1'];
    $headers = ['Authorization' => 'Bearer invalid-token'];

    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', $headers)->assertUnauthorized();
    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', $headers)->assertUnauthorized();
    $this->withServerVariables($server)->getJson('/api/v1/worker/clients', $headers)
        ->assertTooManyRequests()
        ->assertJsonPath('error.code', 'rate_limit_exceeded');
});

it('keys authenticated throttling on worker identity despite forwarded IP rotation', function () {
    config()->set('services.worker.throttle_per_minute', 1);

    $this->withHeaders(['X-Forwarded-For' => '198.51.100.1'])
        ->getJson('/api/v1/worker/clients', workerHeaders())
        ->assertOk();
    $this->withHeaders(['X-Forwarded-For' => '203.0.113.9'])
        ->getJson('/api/v1/worker/clients', workerHeaders())
        ->assertTooManyRequests()
        ->assertJsonPath('error.code', 'rate_limit_exceeded');
});

it('returns structured errors for PHP upload failures and oversized request bodies', function () {
    $meeting = createWorkerMeeting($this);
    $failedUpload = new \Illuminate\Http\UploadedFile(
        __FILE__,
        'video.mp4',
        'video/mp4',
        UPLOAD_ERR_INI_SIZE,
        true,
    );

    $this->post(
        "/api/v1/worker/meetings/{$meeting->id}/artifacts/video",
        ['file' => $failedUpload],
        workerHeaders(),
    )
        ->assertUnprocessable()
        ->assertJsonPath('error.code', 'validation_failed');

    \Illuminate\Support\Facades\Route::get(
        '/api/v1/worker/test-payload-too-large',
        fn () => throw new \Illuminate\Http\Exceptions\PostTooLargeException,
    )->middleware(['worker.token']);

    $this->getJson('/api/v1/worker/test-payload-too-large', workerHeaders())
        ->assertStatus(413)
        ->assertJsonPath('error.code', 'payload_too_large');
});
