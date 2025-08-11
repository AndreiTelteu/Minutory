<?php

use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;

it('can filter meetings by multiple criteria simultaneously', function () {
    $client1 = Client::factory()->create(['name' => 'Alpha Corp']);
    $client2 = Client::factory()->create(['name' => 'Beta Corp']);
    
    // Create meetings with different statuses and dates
    $meeting1 = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Alpha Completed Meeting',
        'status' => 'completed',
        'uploaded_at' => now()->subDays(2)
    ]);
    
    $meeting2 = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Alpha Pending Meeting',
        'status' => 'pending',
        'uploaded_at' => now()->subDays(1)
    ]);
    
    $meeting3 = Meeting::factory()->create([
        'client_id' => $client2->id,
        'title' => 'Beta Completed Meeting',
        'status' => 'completed',
        'uploaded_at' => now()->subDays(1)
    ]);

    // Test meetings index without filters
    $response = $this->get(route('meetings.index'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 3)
    );

    // Test filtering by client
    $response = $this->get(route('meetings.index', ['client_id' => $client1->id]));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 2)
             ->where('meetings.data.0.client_id', $client1->id)
             ->where('meetings.data.1.client_id', $client1->id)
    );

    // Test filtering by status
    $response = $this->get(route('meetings.index', ['status' => 'completed']));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 2)
             ->where('meetings.data.0.status', 'completed')
             ->where('meetings.data.1.status', 'completed')
    );

    // Test filtering by client AND status
    $response = $this->get(route('meetings.index', [
        'client_id' => $client1->id,
        'status' => 'completed'
    ]));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 1)
             ->where('meetings.data.0.title', 'Alpha Completed Meeting')
             ->where('meetings.data.0.client_id', $client1->id)
             ->where('meetings.data.0.status', 'completed')
    );

    // Test filtering by date range
    $response = $this->get(route('meetings.index', [
        'date_from' => now()->subDays(3)->format('Y-m-d'),
        'date_to' => now()->subDays(2)->format('Y-m-d')
    ]));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 1)
             ->where('meetings.data.0.title', 'Alpha Completed Meeting')
    );
});

it('can search meetings by title and transcription content', function () {
    $client = Client::factory()->create();
    
    $meeting1 = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Budget Planning Session'
    ]);
    
    $meeting2 = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Marketing Strategy Review'
    ]);
    
    $meeting3 = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Team Standup'
    ]);
    
    // Add transcriptions for content search
    Transcription::factory()->create([
        'meeting_id' => $meeting3->id,
        'text' => 'We discussed the budget allocation for the new project.'
    ]);

    // Test search by title
    $response = $this->get(route('meetings.index', ['search' => 'Budget']));
    $response->assertStatus(200);
    
    // Test search by transcription content (if implemented)
    $response = $this->get(route('meetings.index', ['search' => 'Marketing']));
    $response->assertStatus(200);
});

it('can sort meetings by different criteria', function () {
    $client = Client::factory()->create();
    
    $oldMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Old Meeting',
        'uploaded_at' => now()->subDays(5)
    ]);
    
    $recentMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Recent Meeting',
        'uploaded_at' => now()->subDays(1)
    ]);
    
    $middleMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Middle Meeting',
        'uploaded_at' => now()->subDays(3)
    ]);

    // Test default sort (newest first)
    $response = $this->get(route('meetings.index'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 3)
    );

    // Test sort by oldest first
    $response = $this->get(route('meetings.index', ['sort' => 'uploaded_at', 'direction' => 'asc']));
    $response->assertStatus(200);

    // Test sort by title
    $response = $this->get(route('meetings.index', ['sort' => 'title', 'direction' => 'asc']));
    $response->assertStatus(200);
});

it('can perform advanced search with multiple filters', function () {
    $client1 = Client::factory()->create(['name' => 'Important Client']);
    $client2 = Client::factory()->create(['name' => 'Regular Client']);
    
    $meeting1 = Meeting::factory()->completed()->create([
        'client_id' => $client1->id,
        'title' => 'Important Meeting',
        'uploaded_at' => now()->subDays(2)
    ]);
    
    $meeting2 = Meeting::factory()->pending()->create([
        'client_id' => $client2->id,
        'title' => 'Regular Meeting',
        'uploaded_at' => now()->subDays(1)
    ]);

    // Test multiple filters combined
    $response = $this->get(route('meetings.index', [
        'client_id' => $client1->id,
        'status' => 'completed',
        'date_from' => now()->subDays(7)->format('Y-m-d'),
        'date_to' => now()->format('Y-m-d')
    ]));
    
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Index')
             ->has('meetings.data', 1)
             ->where('meetings.data.0.title', 'Important Meeting')
    );
});

it('can handle global search across all content types', function () {
    $client1 = Client::factory()->create(['name' => 'Global Client 1']);
    $client2 = Client::factory()->create(['name' => 'Global Client 2']);
    
    $meeting1 = Meeting::factory()->completed()->create([
        'client_id' => $client1->id,
        'title' => 'Innovation Discussion'
    ]);
    
    $meeting2 = Meeting::factory()->completed()->create([
        'client_id' => $client2->id,
        'title' => 'Strategy Session'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting1->id,
        'speaker' => 'John',
        'text' => 'We need to focus on innovation and new technologies.'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting2->id,
        'speaker' => 'Jane',
        'text' => 'Innovation is key to our future success.'
    ]);

    // Test global search through AI search endpoint
    $response = $this->postJson(route('ai.search'), [
        'query' => 'innovation'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(2);
    expect($data['results'][0]['meeting_title'])->toBe('Innovation Discussion');
    expect($data['results'][1]['meeting_title'])->toBe('Strategy Session');
});

it('can filter search results by date range and content type', function () {
    $client = Client::factory()->create();
    
    $oldMeeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Old Strategy Meeting',
        'uploaded_at' => now()->subDays(10)
    ]);
    
    $recentMeeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Recent Strategy Meeting',
        'uploaded_at' => now()->subDays(2)
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $oldMeeting->id,
        'text' => 'Old strategy discussion about market expansion.'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $recentMeeting->id,
        'text' => 'Recent strategy discussion about product development.'
    ]);

    // Test search with date filter
    $response = $this->postJson(route('ai.search'), [
        'query' => 'strategy',
        'date_from' => now()->subDays(5)->format('Y-m-d')
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    // Should only return recent meeting
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['meeting_title'])->toBe('Recent Strategy Meeting');
});