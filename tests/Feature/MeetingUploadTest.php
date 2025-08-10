<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;

beforeEach(function () {
    Storage::fake('public');
});

it('can display the meeting upload form', function () {
    $client = Client::factory()->create();
    
    $response = $this->get(route('meetings.create'));
    
    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Create')
            ->has('clients', 1)
            ->where('clients.0.id', $client->id)
        );
});

it('can upload a meeting video successfully', function () {
    $client = Client::factory()->create();
    $videoFile = UploadedFile::fake()->create('test-meeting.mp4', 1024, 'video/mp4');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $videoFile,
    ]);
    
    $response->assertRedirect(route('meetings.index'))
        ->assertSessionHas('success', 'Meeting uploaded successfully and is being processed.');
    
    $this->assertDatabaseHas('meetings', [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'status' => 'pending',
    ]);
    
    $meeting = Meeting::where('title', 'Test Meeting')->first();
    expect($meeting->video_path)->toContain("meetings/{$client->id}/{$meeting->id}/video.mp4");
    
    Storage::disk('public')->assertExists($meeting->video_path);
});

it('validates required fields when uploading a meeting', function () {
    $response = $this->post(route('meetings.store'), []);
    
    $response->assertSessionHasErrors(['title', 'client_id', 'video']);
});

it('validates video file format', function () {
    $client = Client::factory()->create();
    $invalidFile = UploadedFile::fake()->create('test.txt', 1024, 'text/plain');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $invalidFile,
    ]);
    
    $response->assertSessionHasErrors(['video']);
});

it('validates video file size limits', function () {
    $client = Client::factory()->create();
    $largeFile = UploadedFile::fake()->create('large-video.mp4', 600 * 1024, 'video/mp4'); // 600MB
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $largeFile,
    ]);
    
    $response->assertSessionHasErrors(['video']);
});

it('validates client exists', function () {
    $videoFile = UploadedFile::fake()->create('test-meeting.mp4', 1024, 'video/mp4');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => 999, // Non-existent client
        'video' => $videoFile,
    ]);
    
    $response->assertSessionHasErrors(['client_id']);
});

it('can display meetings list with filtering', function () {
    $client1 = Client::factory()->create(['name' => 'Client A']);
    $client2 = Client::factory()->create(['name' => 'Client B']);
    
    $meeting1 = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Meeting 1',
        'status' => 'completed'
    ]);
    
    $meeting2 = Meeting::factory()->create([
        'client_id' => $client2->id,
        'title' => 'Meeting 2',
        'status' => 'pending'
    ]);
    
    $response = $this->get(route('meetings.index'));
    
    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Index')
            ->has('meetings.data', 2)
            ->has('clients', 2)
        );
});

it('can filter meetings by client', function () {
    $client1 = Client::factory()->create();
    $client2 = Client::factory()->create();
    
    $meeting1 = Meeting::factory()->create(['client_id' => $client1->id]);
    $meeting2 = Meeting::factory()->create(['client_id' => $client2->id]);
    
    $response = $this->get(route('meetings.index', ['client_id' => $client1->id]));
    
    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Index')
            ->has('meetings.data', 1)
            ->where('meetings.data.0.client_id', $client1->id)
        );
});

it('can display meeting details', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'completed'
    ]);
    
    $response = $this->get(route('meetings.show', $meeting));
    
    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Show')
            ->where('meeting.id', $meeting->id)
            ->where('meeting.title', $meeting->title)
        );
});

it('can delete a meeting and its video file', function () {
    Storage::fake('public');
    
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'video_path' => "meetings/{$client->id}/1/video.mp4"
    ]);
    
    // Create a fake video file
    Storage::disk('public')->put($meeting->video_path, 'fake video content');
    Storage::disk('public')->assertExists($meeting->video_path);
    
    $response = $this->delete(route('meetings.destroy', $meeting));
    
    $response->assertRedirect(route('meetings.index'))
        ->assertSessionHas('success', 'Meeting deleted successfully.');
    
    $this->assertDatabaseMissing('meetings', ['id' => $meeting->id]);
    Storage::disk('public')->assertMissing($meeting->video_path);
});

it('organizes video files by client and meeting ID', function () {
    $client = Client::factory()->create();
    $videoFile = UploadedFile::fake()->create('test-meeting.mp4', 1024, 'video/mp4');
    
    $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $videoFile,
    ]);
    
    $meeting = Meeting::where('title', 'Test Meeting')->first();
    
    expect($meeting->video_path)->toBe("meetings/{$client->id}/{$meeting->id}/video.mp4");
    Storage::disk('public')->assertExists($meeting->video_path);
});