<?php

use App\Models\Client;
use App\Models\Meeting;

it('can filter meetings by status via HTTP request', function () {
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

    $response = $this->get('/meetings?status=pending');
    
    $response->assertStatus(200);
    $response->assertSee($pendingMeeting->title);
    $response->assertDontSee($completedMeeting->title);
});

it('can filter meetings by client via HTTP request', function () {
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

    $response = $this->get("/meetings?client_id={$client1->id}");
    
    $response->assertStatus(200);
    $response->assertSee($meeting1->title);
    $response->assertDontSee($meeting2->title);
});

it('can filter meetings by date range via HTTP request', function () {
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

    $dateFrom = now()->subDays(2)->format('Y-m-d');
    $response = $this->get("/meetings?date_from={$dateFrom}");
    
    $response->assertStatus(200);
    $response->assertSee($recentMeeting->title);
    $response->assertDontSee($oldMeeting->title);
});

it('can combine multiple filters', function () {
    $client1 = Client::factory()->create(['name' => 'Client 1']);
    $client2 = Client::factory()->create(['name' => 'Client 2']);
    
    $targetMeeting = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Target Meeting',
        'status' => 'completed',
        'uploaded_at' => now()->subDays(1)
    ]);
    
    $wrongClientMeeting = Meeting::factory()->create([
        'client_id' => $client2->id,
        'title' => 'Wrong Client Meeting',
        'status' => 'completed',
        'uploaded_at' => now()->subDays(1)
    ]);
    
    $wrongStatusMeeting = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Wrong Status Meeting',
        'status' => 'pending',
        'uploaded_at' => now()->subDays(1)
    ]);

    $dateFrom = now()->subDays(2)->format('Y-m-d');
    $response = $this->get("/meetings?client_id={$client1->id}&status=completed&date_from={$dateFrom}");
    
    $response->assertStatus(200);
    $response->assertSee($targetMeeting->title);
    $response->assertDontSee($wrongClientMeeting->title);
    $response->assertDontSee($wrongStatusMeeting->title);
});