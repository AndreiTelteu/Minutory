<?php

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;
use App\Services\TranscriptImporter;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

uses(RefreshDatabase::class);

function linuxTranscriptPayload(array $segments): string
{
    return json_encode([
        'driver' => 'parakeet',
        'model' => 'nemo-parakeet-tdt-0.6b-v3',
        'language' => 'ro',
        'language_probability' => null,
        'duration' => 2,
        'runtime' => (object) [],
        'segments' => $segments,
    ], JSON_THROW_ON_ERROR);
}

it('updates meeting status to processing and then completed', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'pending',
        'duration' => 60, // 1 minute for faster testing
    ]);

    // Execute the job (this will actually sleep for a short time)
    $job = new TranscribeMeetingJob($meeting);
    $job->handle();

    $meeting->refresh();

    expect($meeting->status)->toBe('completed');
    expect($meeting->processing_started_at)->not->toBeNull();
    expect($meeting->processing_completed_at)->not->toBeNull();
    expect($meeting->transcriptions()->count())->toBeGreaterThan(0);
});

it('dispatches transcription job when meeting is uploaded', function () {
    Queue::fake();

    $client = Client::factory()->create();

    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => \Illuminate\Http\Testing\File::fake()->create('test-video.mp4', 1024),
    ]);

    Queue::assertPushed(TranscribeMeetingJob::class);
});

it('stores generated artifacts beside the uploaded video', function () {
    Storage::fake('public');

    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'video_path' => "meetings/{$client->id}/91/video.mp4",
    ]);

    Storage::disk('public')->put($meeting->video_path, 'video');

    $job = new TranscribeMeetingJob($meeting);
    $method = new ReflectionMethod($job, 'cleanupTempFiles');
    $artifactDirectory = dirname(Storage::disk('public')->path($meeting->video_path));

    File::put($artifactDirectory.'/audio.wav', 'audio');
    File::put($artifactDirectory.'/transcript.json', json_encode(['segments' => []]));
    $method->invoke($job);

    Storage::disk('public')->assertExists($meeting->video_path);
    Storage::disk('public')->assertMissing("meetings/{$client->id}/91/audio.wav");
    Storage::disk('public')->assertExists("meetings/{$client->id}/91/transcript.json");
    expect(File::exists(storage_path("{$meeting->id}/audio.wav")))->toBeFalse()
        ->and(File::exists(storage_path("{$meeting->id}/transcript.json")))->toBeFalse();
});

it('delegates normalized Linux output through the shared transcript importer contract', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'old',
    ]);
    $path = Storage::disk('public')->path('linux-transcript.json');
    File::put($path, linuxTranscriptPayload([
        ['speaker' => 'unknown', 'text' => 'new first', 'start' => 0, 'end' => 1],
        ['speaker' => 'unknown', 'text' => 'new second', 'start' => 1, 'end' => 2],
    ]));

    $count = (new TranscribeMeetingJob($meeting))
        ->importTranscript(app(TranscriptImporter::class), $path);

    expect($count)->toBe(2)
        ->and($meeting->transcriptions()->orderBy('id')->pluck('text')->all())
        ->toBe(['new first', 'new second']);
});

it('preserves Linux transcription rows when delegated normalized output is invalid', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    $old = Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'known good',
    ]);
    $path = Storage::disk('public')->path('invalid-linux-transcript.json');
    File::put($path, '{invalid');

    expect(fn () => (new TranscribeMeetingJob($meeting))
        ->importTranscript(app(TranscriptImporter::class), $path))
        ->toThrow(RuntimeException::class)
        ->and($old->fresh()?->text)->toBe('known good');
});

it('calculates progress tracking attributes correctly', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'duration' => 3600, // 60 minutes (1 hour video)
        'processing_started_at' => now()->subSeconds(30), // Started 30 seconds ago
    ]);

    expect($meeting->elapsed_time)->toBe(30);
    expect($meeting->formatted_elapsed_time)->toBe('0:30');
    expect($meeting->estimated_remaining_time)->toBeGreaterThan(0);
    expect($meeting->processing_progress)->not->toBeNull();
    expect($meeting->processing_progress)->toBeLessThan(100);
});

it('provides status endpoint for real-time updates', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'duration' => 1800, // 30 minutes
        'processing_started_at' => now()->subSeconds(15),
    ]);

    $response = $this->get(route('meetings.status', $meeting));

    $response->assertStatus(200)
        ->assertJsonStructure([
            'id',
            'status',
            'elapsed_time',
            'estimated_remaining_time',
            'processing_progress',
            'formatted_elapsed_time',
            'formatted_estimated_remaining_time',
            'queue_progress',
            'formatted_estimated_processing_time',
        ])
        ->assertJson([
            'id' => $meeting->id,
            'status' => 'processing',
        ]);
});

it('calculates queue progress for pending meetings', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'pending',
        'duration' => 1800, // 30 minutes
        'estimated_processing_time' => 30, // 30 seconds
        'uploaded_at' => now()->subSeconds(15), // Uploaded 15 seconds ago
    ]);

    expect($meeting->queue_progress)->toBeGreaterThan(0);
    expect($meeting->queue_progress)->toBeLessThan(100);
    expect($meeting->formatted_estimated_processing_time)->toBe('0:30');
});

it('stores estimated processing time when meeting is uploaded', function () {
    $client = Client::factory()->create();

    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting with Estimation',
        'client_id' => $client->id,
        'video' => \Illuminate\Http\Testing\File::fake()->create('test-video.mp4', 1024),
    ]);

    $meeting = Meeting::latest()->first();

    expect($meeting->estimated_processing_time)->not->toBeNull();
    expect($meeting->estimated_processing_time)->toBeGreaterThan(0);
    expect($meeting->formatted_estimated_processing_time)->not->toBeNull();
});
