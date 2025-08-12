<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;

uses(RefreshDatabase::class);

beforeEach(function () {
    Storage::fake('public');
});

it('handles meeting upload validation errors gracefully', function () {
    $client = Client::factory()->create();

    $response = $this->post(route('meetings.store'), [
        'title' => '', // Missing title
        'client_id' => $client->id,
        // Missing video file
    ]);

    $response->assertSessionHasErrors(['title', 'video']);
    $response->assertRedirect();
});

it('handles invalid file types with proper error messages', function () {
    $client = Client::factory()->create();
    $invalidFile = UploadedFile::fake()->create('document.pdf', 1000);

    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $invalidFile,
    ]);

    $response->assertSessionHasErrors(['video']);
    $response->assertSessionHasErrorsIn('default', [
        'video' => 'The video must be a file of type: MP4, MOV, AVI, or WebM.'
    ]);
});

it('handles file size validation errors', function () {
    $client = Client::factory()->create();
    $largeFile = UploadedFile::fake()->create('video.mp4', 600 * 1024); // 600MB

    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $largeFile,
    ]);

    $response->assertSessionHasErrors(['video']);
});

it('handles missing client validation', function () {
    $invalidFile = UploadedFile::fake()->create('video.mp4', 1000);

    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => 999, // Non-existent client
        'video' => $invalidFile,
    ]);

    $response->assertSessionHasErrors(['client_id']);
});

it('returns proper error response for meeting status API', function () {
    // Test with non-existent meeting
    $response = $this->getJson(route('meetings.status', ['meeting' => 999]));
    
    $response->assertStatus(404);
});

it('handles AI chat validation errors', function () {
    $response = $this->postJson(route('ai.chat'), [
        'message' => '', // Empty message
    ]);

    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['message']);
});

it('handles AI chat with too long message', function () {
    $longMessage = str_repeat('a', 1001); // Over 1000 character limit

    $response = $this->postJson(route('ai.chat'), [
        'message' => $longMessage,
    ]);

    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['message']);
});

it('stores error information when meeting processing fails', function () {
    $meeting = Meeting::factory()->create([
        'status' => 'failed',
        'error_message' => 'Test error message',
        'technical_error' => 'Technical details here'
    ]);

    expect($meeting->error_message)->toBe('Test error message');
    expect($meeting->technical_error)->toBe('Technical details here');
    expect($meeting->isFailed())->toBeTrue();
});

it('handles meeting show with missing video file gracefully', function () {
    $meeting = Meeting::factory()->create([
        'video_path' => 'non-existent-path.mp4'
    ]);

    $response = $this->get(route('meetings.show', $meeting));

    $response->assertOk();
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Show')
             ->has('videoError')
    );
});

it('provides proper error context in meeting status response', function () {
    $meeting = Meeting::factory()->create([
        'status' => 'processing'
    ]);

    $response = $this->getJson(route('meetings.status', $meeting));

    $response->assertOk();
    $response->assertJsonStructure([
        'success',
        'data' => [
            'id',
            'status',
            'elapsed_time',
            'estimated_remaining_time',
            'processing_progress',
            'formatted_elapsed_time',
            'formatted_estimated_remaining_time',
            'queue_progress',
            'formatted_estimated_processing_time'
        ]
    ]);
});