<?php

use App\Models\Client;
use App\Models\Meeting;
use App\Jobs\TranscribeMeetingJob;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Queue;

beforeEach(function () {
    Storage::fake('public');
    Queue::fake();
});

it('can complete the full meeting upload workflow', function () {
    $client = Client::factory()->create(['name' => 'Test Client']);

    // Test meeting creation form display
    $response = $this->get(route('meetings.create'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Create')
             ->has('clients', 1)
             ->where('clients.0.id', $client->id)
    );

    // Test meeting upload
    $videoFile = UploadedFile::fake()->create('quarterly-review.mp4', 1024, 'video/mp4');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Quarterly Review Meeting',
        'client_id' => $client->id,
        'video' => $videoFile,
    ]);
    
    $response->assertRedirect(route('meetings.index'));
    $response->assertSessionHas('success', 'Meeting uploaded successfully and is being processed.');
    
    // Verify meeting was created
    $this->assertDatabaseHas('meetings', [
        'title' => 'Quarterly Review Meeting',
        'client_id' => $client->id,
        'status' => 'pending',
    ]);
    
    $meeting = Meeting::where('title', 'Quarterly Review Meeting')->first();
    expect($meeting->video_path)->toContain("meetings/{$client->id}/{$meeting->id}/video.mp4");
    
    // Verify file was stored
    Storage::disk('public')->assertExists($meeting->video_path);
    
    // Verify transcription job was dispatched
    Queue::assertPushed(TranscribeMeetingJob::class, function ($job) use ($meeting) {
        return $job->meeting->id === $meeting->id;
    });

    // Test meetings list display
    $response = $this->get(route('meetings.index'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 1)
             ->where('meetings.data.0.title', 'Quarterly Review Meeting')
             ->where('meetings.data.0.status', 'pending')
    );
});

it('shows upload progress during file upload')
    ->browse(function ($browser) {
        $client = Client::factory()->create();

        $browser->visit('/meetings/create')
                ->type('[data-testid="meeting-title"]', 'Large Meeting File')
                ->select('[data-testid="client-selector"]', $client->id)
                ->attach('[data-testid="video-upload"]', storage_path('test-files/large-video.mp4'))
                ->click('[data-testid="upload-button"]')
                ->waitFor('[data-testid="upload-progress"]', 5)
                ->assertSee('Uploading')
                ->assertVisible('[data-testid="progress-bar"]')
                ->waitFor('[data-testid="upload-complete"]', 30)
                ->assertSee('Upload complete');
    });

it('validates meeting upload form')
    ->browse(function ($browser) {
        $browser->visit('/meetings/create')
                ->click('[data-testid="upload-button"]')
                ->assertSee('The title field is required')
                ->assertSee('The client field is required')
                ->assertSee('The video field is required')
                ->type('[data-testid="meeting-title"]', 'Test Meeting')
                ->attach('[data-testid="video-upload"]', storage_path('test-files/invalid-file.txt'))
                ->click('[data-testid="upload-button"]')
                ->assertSee('The video must be a file of type: mp4, mov, avi, webm');
    });

it('tracks meeting processing status in real-time')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Processing Meeting',
            'status' => 'processing',
            'processing_started_at' => now()->subMinutes(2),
            'duration' => 1800, // 30 minutes
            'estimated_processing_time' => 30 // 30 seconds
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->assertSee('Processing')
                ->assertSee('Elapsed:')
                ->assertSee('Remaining:')
                ->assertVisible('[data-testid="processing-indicator"]')
                ->waitFor('[data-testid="status-update"]', 5) // Wait for status update
                ->assertSee('2:'); // Should show elapsed time in minutes
    });

it('shows queue position for pending meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        
        // Create multiple pending meetings to simulate queue
        $meeting1 = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'First Meeting',
            'status' => 'pending',
            'uploaded_at' => now()->subMinutes(5)
        ]);
        
        $meeting2 = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Second Meeting',
            'status' => 'pending',
            'uploaded_at' => now()->subMinutes(3)
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting1->title)
                ->assertSee($meeting2->title)
                ->assertSee('In Queue')
                ->assertSee('Position: 1') // First meeting should be position 1
                ->assertSee('Position: 2') // Second meeting should be position 2
                ->assertSee('Est. processing time:');
    });

it('updates status when meeting processing completes')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Completing Meeting',
            'status' => 'processing',
            'processing_started_at' => now()->subMinutes(1)
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->assertSee('Processing')
                ->pause(2000) // Wait for potential status update
                ->refresh() // Simulate real-time update
                ->assertSee($meeting->title);
        
        // Simulate completion
        $meeting->update([
            'status' => 'completed',
            'processing_completed_at' => now()
        ]);
        
        $browser->refresh()
                ->assertSee('Completed')
                ->assertDontSee('Processing')
                ->assertVisible('[data-testid="view-meeting-button"]');
    });

it('handles processing failures gracefully')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Failed Meeting',
            'status' => 'failed'
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->assertSee('Failed')
                ->assertVisible('[data-testid="retry-button"]')
                ->click('[data-testid="retry-button"]')
                ->assertSee('Processing restarted')
                ->assertSee('Processing'); // Status should change to processing
    });

it('can filter meetings by processing status')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        
        $pendingMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Pending Meeting',
            'status' => 'pending'
        ]);
        
        $processingMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Processing Meeting',
            'status' => 'processing'
        ]);
        
        $completedMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Completed Meeting',
            'status' => 'completed'
        ]);

        $browser->visit('/meetings')
                ->assertSee($pendingMeeting->title)
                ->assertSee($processingMeeting->title)
                ->assertSee($completedMeeting->title)
                ->select('[data-testid="status-filter"]', 'pending')
                ->click('[data-testid="apply-filters"]')
                ->assertSee($pendingMeeting->title)
                ->assertDontSee($processingMeeting->title)
                ->assertDontSee($completedMeeting->title)
                ->select('[data-testid="status-filter"]', 'completed')
                ->click('[data-testid="apply-filters"]')
                ->assertSee($completedMeeting->title)
                ->assertDontSee($pendingMeeting->title)
                ->assertDontSee($processingMeeting->title);
    });

it('shows detailed processing information')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Detailed Processing Meeting',
            'status' => 'processing',
            'processing_started_at' => now()->subMinutes(3),
            'duration' => 2400, // 40 minutes
            'estimated_processing_time' => 40 // 40 seconds
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->click("[data-testid=\"meeting-details-{$meeting->id}\"]")
                ->assertSee('Processing Details')
                ->assertSee('Started:')
                ->assertSee('Elapsed Time:')
                ->assertSee('Estimated Remaining:')
                ->assertSee('Video Duration: 40:00')
                ->assertSee('Processing Progress:')
                ->assertVisible('[data-testid="progress-bar"]');
    });

it('can cancel processing meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Cancellable Meeting',
            'status' => 'processing',
            'processing_started_at' => now()->subMinutes(1)
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->assertSee('Processing')
                ->click("[data-testid=\"cancel-processing-{$meeting->id}\"]")
                ->assertDialogOpened('Are you sure you want to cancel processing?')
                ->acceptDialog()
                ->assertSee('Processing cancelled')
                ->assertSee('Pending'); // Should revert to pending status
    });it('can
 validate meeting upload form and handle errors', function () {
    // Test validation errors
    $response = $this->post(route('meetings.store'), []);
    $response->assertSessionHasErrors(['title', 'client_id', 'video']);

    // Test invalid file format
    $client = Client::factory()->create();
    $invalidFile = UploadedFile::fake()->create('test.txt', 1024, 'text/plain');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $invalidFile,
    ]);
    $response->assertSessionHasErrors(['video']);

    // Test file size validation
    $largeFile = UploadedFile::fake()->create('large-video.mp4', 600 * 1024, 'video/mp4'); // 600MB
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $largeFile,
    ]);
    $response->assertSessionHasErrors(['video']);

    // Test non-existent client
    $videoFile = UploadedFile::fake()->create('test-meeting.mp4', 1024, 'video/mp4');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => 999, // Non-existent client
        'video' => $videoFile,
    ]);
    $response->assertSessionHasErrors(['client_id']);
});

it('can track meeting processing status and progress', function () {
    $client = Client::factory()->create();
    
    // Test pending meeting status
    $pendingMeeting = Meeting::factory()->pending()->create([
        'client_id' => $client->id,
        'title' => 'Pending Meeting',
        'estimated_processing_time' => 30
    ]);

    $response = $this->get("/meetings/{$pendingMeeting->id}/status");
    $response->assertStatus(200);
    $response->assertJsonStructure([
        'id',
        'status',
        'queue_progress',
        'formatted_estimated_processing_time'
    ]);
    
    $data = $response->json();
    expect($data['status'])->toBe('pending');

    // Test processing meeting status
    $processingMeeting = Meeting::factory()->processing()->create([
        'client_id' => $client->id,
        'title' => 'Processing Meeting',
        'duration' => 1800, // 30 minutes
        'estimated_processing_time' => 30 // 30 seconds
    ]);

    $response = $this->get("/meetings/{$processingMeeting->id}/status");
    $response->assertStatus(200);
    $response->assertJsonStructure([
        'id',
        'status',
        'elapsed_time',
        'estimated_remaining_time',
        'processing_progress',
        'formatted_elapsed_time',
        'formatted_estimated_remaining_time'
    ]);
    
    $data = $response->json();
    expect($data['status'])->toBe('processing');
    expect($data['elapsed_time'])->toBeGreaterThan(0);

    // Test completed meeting status
    $completedMeeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Completed Meeting'
    ]);

    $response = $this->get("/meetings/{$completedMeeting->id}/status");
    $response->assertStatus(200);
    
    $data = $response->json();
    expect($data['status'])->toBe('completed');
});

it('can handle meeting deletion and file cleanup', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'video_path' => "meetings/{$client->id}/1/video.mp4"
    ]);
    
    // Create a fake video file
    Storage::disk('public')->put($meeting->video_path, 'fake video content');
    Storage::disk('public')->assertExists($meeting->video_path);
    
    $response = $this->delete(route('meetings.destroy', $meeting));
    
    $response->assertRedirect(route('meetings.index'));
    $response->assertSessionHas('success', 'Meeting deleted successfully.');
    
    $this->assertDatabaseMissing('meetings', ['id' => $meeting->id]);
    Storage::disk('public')->assertMissing($meeting->video_path);
});

it('can organize video files by client and meeting structure', function () {
    $client = Client::factory()->create();
    $videoFile = UploadedFile::fake()->create('test-meeting.mp4', 1024, 'video/mp4');
    
    $response = $this->post(route('meetings.store'), [
        'title' => 'Test Meeting',
        'client_id' => $client->id,
        'video' => $videoFile,
    ]);
    
    $meeting = Meeting::where('title', 'Test Meeting')->first();
    
    expect($meeting->video_path)->toBe("meetings/{$client->id}/{$meeting->id}/video.mp4");
    Storage::disk('public')->assertExists($meeting->video_path);
});