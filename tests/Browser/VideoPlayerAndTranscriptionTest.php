<?php

use App\Models\Client;
use App\Models\Meeting;
use App\Models\Transcription;

it('can display meeting with video player and transcription data', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Video Test Meeting',
        'duration' => 1800 // 30 minutes
    ]);
    
    // Create transcription segments
    $transcription1 = Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'John Doe',
        'text' => 'Welcome everyone to today\'s meeting.',
        'start_time' => 5.0,
        'end_time' => 8.5,
        'confidence' => 0.95
    ]);
    
    $transcription2 = Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Jane Smith',
        'text' => 'Thank you John. Let\'s start with the agenda.',
        'start_time' => 30.0,
        'end_time' => 34.2,
        'confidence' => 0.92
    ]);
    
    $transcription3 = Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'John Doe',
        'text' => 'First item is the budget review.',
        'start_time' => 60.0,
        'end_time' => 63.5,
        'confidence' => 0.88
    ]);

    // Test meeting detail page
    $response = $this->get(route('meetings.show', $meeting));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Show')
             ->where('meeting.id', $meeting->id)
             ->where('meeting.title', 'Video Test Meeting')
             ->where('meeting.status', 'completed')
             ->has('meeting.transcriptions', 3)
             ->where('meeting.transcriptions.0.speaker', 'John Doe')
             ->where('meeting.transcriptions.0.text', 'Welcome everyone to today\'s meeting.')
             ->where('meeting.transcriptions.0.start_time', 5.0)
             ->where('meeting.transcriptions.1.speaker', 'Jane Smith')
             ->where('meeting.transcriptions.2.text', 'First item is the budget review.')
    );
});

it('highlights current transcription segment during video playback')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Highlight Test Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Speaker 1',
            'text' => 'This is the first segment.',
            'start_time' => 10.0,
            'end_time' => 15.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Speaker 2',
            'text' => 'This is the second segment.',
            'start_time' => 20.0,
            'end_time' => 25.0
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertVisible('[data-testid="video-player"]')
                ->click('[data-testid="play-button"]')
                ->pause(1000)
                ->click('[data-testid="timestamp-10.0"]') // Jump to first segment
                ->pause(2000)
                ->assertHasClass('[data-testid="transcription-segment-10.0"]', 'highlighted')
                ->assertDoesntHaveClass('[data-testid="transcription-segment-20.0"]', 'highlighted')
                ->click('[data-testid="timestamp-20.0"]') // Jump to second segment
                ->pause(2000)
                ->assertHasClass('[data-testid="transcription-segment-20.0"]', 'highlighted')
                ->assertDoesntHaveClass('[data-testid="transcription-segment-10.0"]', 'highlighted');
    });

it('can control video playback with keyboard shortcuts')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Keyboard Test Meeting'
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertVisible('[data-testid="video-player"]')
                ->click('[data-testid="video-player"]') // Focus the video player
                ->keys('[data-testid="video-player"]', ' ') // Spacebar to play/pause
                ->pause(1000)
                ->assertScript('!document.querySelector("[data-testid=video-player] video").paused', true) // Should be playing
                ->keys('[data-testid="video-player"]', ' ') // Spacebar to pause
                ->pause(500)
                ->assertScript('document.querySelector("[data-testid=video-player] video").paused', true) // Should be paused
                ->keys('[data-testid="video-player"]', ['{ARROW_RIGHT}']) // Right arrow to skip forward
                ->pause(500)
                ->keys('[data-testid="video-player"]', ['{ARROW_LEFT}']) // Left arrow to skip backward
                ->pause(500);
    });

it('can adjust playback speed')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Speed Test Meeting'
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertVisible('[data-testid="video-player"]')
                ->click('[data-testid="playback-speed-button"]')
                ->assertVisible('[data-testid="speed-menu"]')
                ->click('[data-testid="speed-1.5x"]')
                ->assertScript('document.querySelector("[data-testid=video-player] video").playbackRate', 1.5)
                ->click('[data-testid="playback-speed-button"]')
                ->click('[data-testid="speed-2x"]')
                ->assertScript('document.querySelector("[data-testid=video-player] video").playbackRate', 2.0)
                ->click('[data-testid="playback-speed-button"]')
                ->click('[data-testid="speed-0.5x"]')
                ->assertScript('document.querySelector("[data-testid=video-player] video").playbackRate', 0.5);
    });

it('can search within transcription text')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Search Test Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'John',
            'text' => 'We need to discuss the budget allocation for next quarter.',
            'start_time' => 10.0,
            'end_time' => 15.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Jane',
            'text' => 'The marketing budget should be increased significantly.',
            'start_time' => 30.0,
            'end_time' => 35.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Bob',
            'text' => 'I agree with the budget proposal.',
            'start_time' => 50.0,
            'end_time' => 53.0
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertVisible('[data-testid="transcription-search"]')
                ->type('[data-testid="transcription-search"]', 'budget')
                ->click('[data-testid="search-transcription-button"]')
                ->assertSee('3 results found')
                ->assertHasClass('[data-testid="transcription-segment-10.0"]', 'search-highlight')
                ->assertHasClass('[data-testid="transcription-segment-30.0"]', 'search-highlight')
                ->assertHasClass('[data-testid="transcription-segment-50.0"]', 'search-highlight')
                ->click('[data-testid="next-search-result"]')
                ->assertScript('Math.floor(document.querySelector("[data-testid=video-player] video").currentTime)', 10)
                ->click('[data-testid="next-search-result"]')
                ->assertScript('Math.floor(document.querySelector("[data-testid=video-player] video").currentTime)', 30);
    });

it('can filter transcription by speaker')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Speaker Filter Test Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Alice Johnson',
            'text' => 'This is Alice speaking.',
            'start_time' => 10.0,
            'end_time' => 13.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Bob Wilson',
            'text' => 'This is Bob speaking.',
            'start_time' => 20.0,
            'end_time' => 23.0
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Alice Johnson',
            'text' => 'Alice speaking again.',
            'start_time' => 30.0,
            'end_time' => 33.0
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertSee('This is Alice speaking')
                ->assertSee('This is Bob speaking')
                ->assertSee('Alice speaking again')
                ->select('[data-testid="speaker-filter"]', 'Alice Johnson')
                ->assertSee('This is Alice speaking')
                ->assertDontSee('This is Bob speaking')
                ->assertSee('Alice speaking again')
                ->select('[data-testid="speaker-filter"]', 'Bob Wilson')
                ->assertDontSee('This is Alice speaking')
                ->assertSee('This is Bob speaking')
                ->assertDontSee('Alice speaking again');
    });

it('can export transcription in different formats')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Export Test Meeting'
        ]);
        
        Transcription::factory()->count(5)->create([
            'meeting_id' => $meeting->id
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertVisible('[data-testid="export-transcription-button"]')
                ->click('[data-testid="export-transcription-button"]')
                ->assertVisible('[data-testid="export-menu"]')
                ->click('[data-testid="export-txt"]')
                ->pause(2000) // Wait for download
                ->click('[data-testid="export-transcription-button"]')
                ->click('[data-testid="export-srt"]')
                ->pause(2000) // Wait for download
                ->click('[data-testid="export-transcription-button"]')
                ->click('[data-testid="export-vtt"]')
                ->pause(2000); // Wait for download
    });

it('shows transcription confidence scores and allows filtering')
    ->browse(function ($browser) {
        $client = Client::factory()->create();
        $meeting = Meeting::factory()->completed()->create([
            'client_id' => $client->id,
            'title' => 'Confidence Test Meeting'
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Clear Speaker',
            'text' => 'This is very clear audio.',
            'start_time' => 10.0,
            'end_time' => 13.0,
            'confidence' => 0.95
        ]);
        
        Transcription::factory()->create([
            'meeting_id' => $meeting->id,
            'speaker' => 'Unclear Speaker',
            'text' => 'This is unclear audio.',
            'start_time' => 20.0,
            'end_time' => 23.0,
            'confidence' => 0.65
        ]);

        $browser->visit("/meetings/{$meeting->id}")
                ->assertSee('This is very clear audio')
                ->assertSee('This is unclear audio')
                ->assertVisible('[data-testid="confidence-95"]') // High confidence indicator
                ->assertVisible('[data-testid="confidence-65"]') // Low confidence indicator
                ->check('[data-testid="show-confidence-scores"]')
                ->assertSee('95%')
                ->assertSee('65%')
                ->select('[data-testid="confidence-filter"]', 'high') // Filter for high confidence only
                ->assertSee('This is very clear audio')
                ->assertDontSee('This is unclear audio');
    });it
('can search within transcription text and filter by speaker', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Search Test Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'John',
        'text' => 'We need to discuss the budget allocation for next quarter.',
        'start_time' => 10.0,
        'end_time' => 15.0
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Jane',
        'text' => 'The marketing budget should be increased significantly.',
        'start_time' => 30.0,
        'end_time' => 35.0
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Bob',
        'text' => 'I agree with the budget proposal.',
        'start_time' => 50.0,
        'end_time' => 53.0
    ]);

    // Test that meeting page loads with all transcriptions
    $response = $this->get(route('meetings.show', $meeting));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Show')
             ->has('meeting.transcriptions', 3)
             ->where('meeting.transcriptions.0.text', 'We need to discuss the budget allocation for next quarter.')
             ->where('meeting.transcriptions.1.speaker', 'Jane')
             ->where('meeting.transcriptions.2.speaker', 'Bob')
    );
});

it('can display transcription confidence scores and metadata', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Confidence Test Meeting'
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Clear Speaker',
        'text' => 'This is very clear audio.',
        'start_time' => 10.0,
        'end_time' => 13.0,
        'confidence' => 0.95
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Unclear Speaker',
        'text' => 'This is unclear audio.',
        'start_time' => 20.0,
        'end_time' => 23.0,
        'confidence' => 0.65
    ]);

    $response = $this->get(route('meetings.show', $meeting));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Show')
             ->has('meeting.transcriptions', 2)
             ->where('meeting.transcriptions.0.confidence', 0.95)
             ->where('meeting.transcriptions.1.confidence', 0.65)
    );
});

it('can handle meetings with no transcriptions', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->pending()->create([
        'client_id' => $client->id,
        'title' => 'No Transcription Meeting'
    ]);

    $response = $this->get(route('meetings.show', $meeting));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Show')
             ->where('meeting.id', $meeting->id)
             ->where('meeting.status', 'pending')
             ->has('meeting.transcriptions', 0)
    );
});

it('can display transcription timing and duration data', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->create([
        'client_id' => $client->id,
        'title' => 'Timing Test Meeting',
        'duration' => 3600 // 1 hour
    ]);
    
    // Create transcriptions with specific timing
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Speaker 1',
        'text' => 'Opening remarks.',
        'start_time' => 0.0,
        'end_time' => 5.5
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Speaker 2',
        'text' => 'Middle discussion.',
        'start_time' => 1800.0, // 30 minutes
        'end_time' => 1820.0
    ]);
    
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'speaker' => 'Speaker 1',
        'text' => 'Closing remarks.',
        'start_time' => 3580.0, // Near end
        'end_time' => 3600.0
    ]);

    $response = $this->get(route('meetings.show', $meeting));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Meetings/Show')
             ->where('meeting.duration', 3600)
             ->has('meeting.transcriptions', 3)
             ->where('meeting.transcriptions.0.start_time', 0.0)
             ->where('meeting.transcriptions.1.start_time', 1800.0)
             ->where('meeting.transcriptions.2.end_time', 3600.0)
    );
});