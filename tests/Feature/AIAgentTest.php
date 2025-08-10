<?php

use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;

it('can access the AI chat interface', function () {
    $response = $this->get('/ai/chat');
    
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => $page->component('AI/Chat'));
});

it('can search through meeting transcriptions directly', function () {
    // Create test data
    $client = Client::factory()->create(['name' => 'Test Client']);
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Budget Planning Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'John Doe',
        'text' => 'We need to discuss the budget allocation for next quarter',
        'start_time' => 30.5,
        'end_time' => 35.2,
        'confidence' => 0.95
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Jane Smith',
        'text' => 'The marketing budget should be increased by 20%',
        'start_time' => 45.1,
        'end_time' => 48.8,
        'confidence' => 0.92
    ]);
    
    // Test search functionality
    $response = $this->postJson('/ai/search', [
        'query' => 'budget',
        'limit' => 10
    ]);
    
    $response->assertStatus(200);
    $response->assertJson([
        'success' => true
    ]);
    
    $data = $response->json('data');
    expect($data['results'])->toHaveCount(2);
    expect($data['total_found'])->toBe(2);
    expect($data['search_query'])->toBe('budget');
    
    // Check first result
    $firstResult = $data['results'][0];
    expect($firstResult['meeting_title'])->toBe('Budget Planning Meeting');
    expect($firstResult['client_name'])->toBe('Test Client');
    expect($firstResult['speaker'])->toBe('John Doe');
    expect($firstResult['text'])->toContain('**budget**');
    expect($firstResult['timestamp'])->toBe(30.5);
});

it('can filter search results by client', function () {
    // Create test data for two different clients
    $client1 = Client::factory()->create(['name' => 'Client One']);
    $client2 = Client::factory()->create(['name' => 'Client Two']);
    
    $meeting1 = Meeting::factory()->completed()->create(['client_id' => $client1->id]);
    $meeting2 = Meeting::factory()->completed()->create(['client_id' => $client2->id]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting1->id,
        'text' => 'Project timeline discussion',
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting2->id,
        'text' => 'Project budget review',
    ]);
    
    // Search with client filter
    $response = $this->postJson('/ai/search', [
        'query' => 'project',
        'client_id' => $client1->id
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['client_name'])->toBe('Client One');
});

it('can filter search results by speaker', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create(['client_id' => $client->id]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Alice Johnson',
        'text' => 'I think we should proceed with the plan',
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Bob Wilson',
        'text' => 'I agree with the plan completely',
    ]);
    
    // Search with speaker filter
    $response = $this->postJson('/ai/search', [
        'query' => 'plan',
        'speaker' => 'Alice'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['speaker'])->toBe('Alice Johnson');
});

it('handles empty search queries gracefully', function () {
    $response = $this->postJson('/ai/search', [
        'query' => '   '  // Whitespace only
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data)->toHaveKey('error');
    expect($data['error'])->toBe('Search query cannot be empty');
});

it('validates search request parameters', function () {
    $response = $this->postJson('/ai/search', []);
    
    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['query']);
});