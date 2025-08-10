<?php

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Queue;
use Illuminate\Support\Facades\Storage;

beforeEach(function () {
    Storage::fake('public');
    Queue::fake();
});

it('can display meetings with status badges and filtering')
    ->browse(function ($browser) {
        $client = Client::factory()->create(['name' => 'Test Client']);
        
        $pendingMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Pending Meeting',
            'status' => 'pending'
        ]);
        
        $processingMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Processing Meeting',
            'status' => 'processing',
            'processing_started_at' => now()->subMinutes(5)
        ]);
        
        $completedMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Completed Meeting',
            'status' => 'completed',
            'processing_completed_at' => now()
        ]);

        $browser->visit('/meetings')
                ->assertSee('Meetings')
                ->assertSee('Live updates active')
                ->assertSee($pendingMeeting->title)
                ->assertSee($processingMeeting->title)
                ->assertSee($completedMeeting->title)
                ->assertSee('Pending')
                ->assertSee('Processing')
                ->assertSee('Completed');
    });

it('can filter meetings by status')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        
        $pendingMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Pending Meeting',
            'status' => 'pending'
        ]);
        
        $completedMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Completed Meeting',
            'status' => 'completed'
        ]);

        $browser->visit('/meetings')
                ->select('[data-testid="status-filter"]', 'pending')
                ->click('button[type="submit"]')
                ->assertSee($pendingMeeting->title)
                ->assertDontSee($completedMeeting->title);
    });

it('can filter meetings by client')
    ->browse(function ($browser) {
        $client1 = Client::factory()->create(['name' => 'Client 1']);
        $client2 = Client::factory()->create(['name' => 'Client 2']);
        
        $meeting1 = Meeting::factory()->create([
            'client_id' => $client1->id,
            'title' => 'Client 1 Meeting'
        ]);
        
        $meeting2 = Meeting::factory()->create([
            'client_id' => $client2->id,
            'title' => 'Client 2 Meeting'
        ]);

        $browser->visit('/meetings')
                ->select('[data-testid="client-filter"]', $client1->id)
                ->click('button[type="submit"]')
                ->assertSee($meeting1->title)
                ->assertDontSee($meeting2->title);
    });

it('can filter meetings by date range')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        
        $oldMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Old Meeting',
            'uploaded_at' => now()->subDays(10)
        ]);
        
        $recentMeeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Recent Meeting',
            'uploaded_at' => now()->subDays(1)
        ]);

        $browser->visit('/meetings')
                ->type('[data-testid="date-from"]', now()->subDays(2)->format('Y-m-d'))
                ->click('button[type="submit"]')
                ->assertSee($recentMeeting->title)
                ->assertDontSee($oldMeeting->title);
    });

it('provides real-time status updates via API endpoint', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'processing_started_at' => now()->subMinutes(2),
        'duration' => 1800, // 30 minutes
        'estimated_processing_time' => 30 // 30 seconds
    ]);

    $response = $this->get("/meetings/{$meeting->id}/status");
    
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
                 'formatted_estimated_processing_time'
             ]);
    
    $data = $response->json();
    expect($data['status'])->toBe('processing');
    expect($data['elapsed_time'])->toBeGreaterThan(0);
    expect($data['formatted_elapsed_time'])->toMatch('/\d+:\d{2}/');
});

it('shows progress indicators for processing meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Processing Meeting',
            'status' => 'processing',
            'processing_started_at' => now()->subMinutes(1),
            'duration' => 600, // 10 minutes
            'estimated_processing_time' => 10 // 10 seconds
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->assertSee('Processing Video')
                ->assertSee('Elapsed:')
                ->assertSee('Remaining:');
    });

it('shows queue progress for pending meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Pending Meeting',
            'status' => 'pending',
            'uploaded_at' => now()->subSeconds(15),
            'estimated_processing_time' => 30
        ]);

        $browser->visit('/meetings')
                ->assertSee($meeting->title)
                ->assertSee('In Queue')
                ->assertSee('Est. processing time:');
    });