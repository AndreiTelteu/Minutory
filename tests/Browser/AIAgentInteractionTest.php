<?php

use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;

it('can access AI chat interface and search through transcriptions', function () {
    $client = Client::factory()->create(['name' => 'Acme Corp']);
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Budget Planning Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'John Doe',
        'text' => 'We need to allocate more budget to marketing this quarter.',
        'start_time' => 30.0,
        'end_time' => 35.0
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Jane Smith',
        'text' => 'The marketing budget should increase by 25% for better ROI.',
        'start_time' => 60.0,
        'end_time' => 65.0
    ]);

    // Test AI chat interface access
    $response = $this->get(route('ai.chat'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => $page->component('AI/Chat'));

    // Test direct search functionality
    $response = $this->postJson(route('ai.search'), [
        'query' => 'marketing budget',
        'limit' => 10
    ]);
    
    $response->assertStatus(200);
    $response->assertJson([
        'success' => true
    ]);
    
    $data = $response->json('data');
    expect(count($data['results']))->toBeGreaterThan(0);
    expect($data['total_found'])->toBeGreaterThan(0);
    expect($data['search_query'])->toBe('marketing budget');
    
    // Check that search results contain expected data
    $firstResult = $data['results'][0];
    expect($firstResult['meeting_title'])->toBe('Budget Planning Meeting');
    expect($firstResult['client_name'])->toBe('Acme Corp');
    expect($firstResult)->toHaveKey('speaker');
    expect($firstResult)->toHaveKey('text');
    expect($firstResult)->toHaveKey('timestamp');
});

it('can click on search results to navigate to meeting timestamps')
    ->browse(function ($browser) {
        $client = Client::factory()->create(['name' => 'Test Client']);
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Project Discussion'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Alice',
            'text' => 'The project timeline needs to be adjusted.',
            'start_time' => 45.0,
            'end_time' => 48.0
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'What was said about project timeline?')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('Project Discussion')
                ->click('[data-testid="result-link-1"]')
                ->assertPathIs("/meetings/{$meeting->id}")
                ->assertScript('Math.floor(document.querySelector("[data-testid=video-player] video").currentTime)', 45)
                ->assertHasClass('[data-testid="transcription-segment-45.0"]', 'highlighted');
    });

it('can filter AI search results by client')
    ->browse(function ($browser) {
        $client1 = Client::factory()->create(['name' => 'Client A']);
        $client2 = Client::factory()->create(['name' => 'Client B']);
        
        $meeting1 = Meeting::factory()->completed()->create([
            'client_id' => $client1->id,
            'title' => 'Client A Meeting'
        ]);
        
        $meeting2 = Meeting::factory()->completed()->create([
            'client_id' => $client2->id,
            'title' => 'Client B Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting1->id,
            'text' => 'We need to discuss the project scope.'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting2->id,
            'text' => 'The project scope is well defined.'
        ]);

        $browser->visit('/ai/chat')
                ->select('[data-testid="client-filter"]', $client1->id)
                ->type('[data-testid="chat-input"]', 'Tell me about project scope')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('Client A Meeting')
                ->assertDontSee('Client B Meeting')
                ->assertSee('Found 1 relevant discussion');
    });

it('can ask follow-up questions in conversation')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Strategy Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'CEO',
            'text' => 'Our revenue target for Q4 is 2 million dollars.',
            'start_time' => 120.0,
            'end_time' => 125.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'CFO',
            'text' => 'We are currently at 1.5 million, so we need 500k more.',
            'start_time' => 130.0,
            'end_time' => 135.0
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'What are our revenue targets?')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('2 million dollars')
                ->assertSee('Q4')
                ->type('[data-testid="chat-input"]', 'How much more do we need to reach that target?')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response-2"]', 10)
                ->assertSee('500k more')
                ->assertSee('1.5 million');
    });

it('can search for specific speakers across meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        
        $meeting1 = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Meeting 1'
        ]);
        
        $meeting2 = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Meeting 2'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting1->id,
            'speaker' => 'Dr. Sarah Johnson',
            'text' => 'The research shows promising results.'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting2->id,
            'speaker' => 'Dr. Sarah Johnson',
            'text' => 'Based on our previous findings, I recommend proceeding.'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting1->id,
            'speaker' => 'Mike Davis',
            'text' => 'I agree with the research findings.'
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'What did Dr. Sarah Johnson say?')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('Found 2 relevant discussions')
                ->assertSee('Dr. Sarah Johnson')
                ->assertSee('research shows promising results')
                ->assertSee('recommend proceeding')
                ->assertDontSee('Mike Davis');
    });

it('can search for action items and decisions')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Action Items Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Manager',
            'text' => 'Action item: John will prepare the quarterly report by Friday.',
            'start_time' => 300.0,
            'end_time' => 305.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Manager',
            'text' => 'Decision: We will proceed with the new marketing campaign.',
            'start_time' => 400.0,
            'end_time' => 405.0
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'What action items were assigned?')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('Action item')
                ->assertSee('John will prepare')
                ->assertSee('quarterly report')
                ->assertSee('Friday')
                ->type('[data-testid="chat-input"]', 'What decisions were made?')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response-2"]', 10)
                ->assertSee('Decision')
                ->assertSee('marketing campaign');
    });

it('handles complex queries with multiple search terms')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Complex Query Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Analyst',
            'text' => 'The Q3 budget analysis shows we overspent on marketing by 15%.',
            'start_time' => 180.0,
            'end_time' => 185.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Director',
            'text' => 'For Q4, we need to reduce marketing spend and focus on ROI.',
            'start_time' => 240.0,
            'end_time' => 245.0
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'Find discussions about Q3 and Q4 marketing budget and ROI')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('Found 2 relevant discussions')
                ->assertSee('Q3 budget analysis')
                ->assertSee('overspent on marketing')
                ->assertSee('Q4')
                ->assertSee('reduce marketing spend')
                ->assertSee('focus on ROI');
    });

it('provides helpful suggestions when no results are found')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Sample Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'text' => 'We discussed the project timeline and deliverables.'
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'Tell me about cryptocurrency investments')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('No relevant discussions found')
                ->assertSee('Try searching for:')
                ->assertSee('project')
                ->assertSee('timeline')
                ->assertSee('deliverables');
    });

it('can export search results and conversation history')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Export Test Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'text' => 'Important discussion about project milestones.'
        ]);

        $browser->visit('/ai/chat')
                ->type('[data-testid="chat-input"]', 'Find project milestones')
                ->click('[data-testid="send-button"]')
                ->waitFor('[data-testid="ai-response"]', 10)
                ->assertSee('project milestones')
                ->click('[data-testid="export-conversation"]')
                ->assertVisible('[data-testid="export-options"]')
                ->click('[data-testid="export-pdf"]')
                ->pause(2000) // Wait for download
                ->click('[data-testid="export-conversation"]')
                ->click('[data-testid="export-json"]')
                ->pause(2000); // Wait for download
    });it('can 
filter AI search results by client and speaker', function () {
    // Create test data for two different clients
    $client1 = Client::factory()->create(['name' => 'Client One']);
    $client2 = Client::factory()->create(['name' => 'Client Two']);
    
    $meeting1 = Meeting::factory()->completed()->create(['client_id' => $client1->id]);
    $meeting2 = Meeting::factory()->completed()->create(['client_id' => $client2->id]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting1->id,
        'speaker' => 'Alice Johnson',
        'text' => 'Project timeline discussion for client one.',
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting2->id,
        'speaker' => 'Bob Wilson',
        'text' => 'Project budget review for client two.',
    ]);

    // Search with client filter
    $response = $this->postJson(route('ai.search'), [
        'query' => 'project',
        'client_id' => $client1->id
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['client_name'])->toBe('Client One');
    expect($data['results'][0]['speaker'])->toBe('Alice Johnson');

    // Search with speaker filter
    $response = $this->postJson(route('ai.search'), [
        'query' => 'project',
        'speaker' => 'Alice'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['speaker'])->toBe('Alice Johnson');
});

it('can search for specific types of content like action items and decisions', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Action Items Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Manager',
        'text' => 'Action item: John will prepare the quarterly report by Friday.',
        'start_time' => 300.0,
        'end_time' => 305.0
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Manager',
        'text' => 'Decision: We will proceed with the new marketing campaign.',
        'start_time' => 400.0,
        'end_time' => 405.0
    ]);

    // Search for action items
    $response = $this->postJson(route('ai.search'), [
        'query' => 'action item'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['text'])->toContain('**action**');
    expect($data['results'][0]['text'])->toContain('**item**');
    expect($data['results'][0]['text'])->toContain('quarterly report');

    // Search for decisions
    $response = $this->postJson(route('ai.search'), [
        'query' => 'decision'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(1);
    expect($data['results'][0]['text'])->toContain('**decision**');
    expect($data['results'][0]['text'])->toContain('marketing campaign');
});

it('can handle complex search queries with multiple terms', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Complex Query Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Analyst',
        'text' => 'The Q3 budget analysis shows we overspent on marketing by 15%.',
        'start_time' => 180.0,
        'end_time' => 185.0
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Director',
        'text' => 'For Q4, we need to reduce marketing spend and focus on ROI.',
        'start_time' => 240.0,
        'end_time' => 245.0
    ]);

    // Search with multiple terms
    $response = $this->postJson(route('ai.search'), [
        'query' => 'Q3 Q4 marketing budget ROI'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(2);
    expect($data['results'][0]['text'])->toContain('**Q3**');
    expect($data['results'][0]['text'])->toContain('**budget**');
    expect($data['results'][0]['text'])->toContain('**marketing**');
    expect($data['results'][1]['text'])->toContain('**Q4**');
    expect($data['results'][1]['text'])->toContain('**ROI**');
});

it('can handle empty search queries and validation', function () {
    // Test empty query
    $response = $this->postJson(route('ai.search'), [
        'query' => '   '  // Whitespace only
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data)->toHaveKey('error');
    expect($data['error'])->toBe('Search query cannot be empty');

    // Test missing query parameter
    $response = $this->postJson(route('ai.search'), []);
    
    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['query']);
});

it('can provide helpful suggestions when no results are found', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Sample Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'We discussed the project timeline and deliverables.'
    ]);

    // Search for something that doesn't exist
    $response = $this->postJson(route('ai.search'), [
        'query' => 'cryptocurrency investments'
    ]);
    
    $response->assertStatus(200);
    $data = $response->json('data');
    
    expect($data['results'])->toHaveCount(0);
    expect($data['total_found'])->toBe(0);
    expect($data)->toHaveKey('suggestions');
});