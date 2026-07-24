<?php

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

uses(RefreshDatabase::class);

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
    Storage::disk('public')->assertMissing("meetings/{$client->id}/91/transcript.json");
    expect(File::exists(storage_path("{$meeting->id}/audio.wav")))->toBeFalse()
        ->and(File::exists(storage_path("{$meeting->id}/transcript.json")))->toBeFalse();
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
