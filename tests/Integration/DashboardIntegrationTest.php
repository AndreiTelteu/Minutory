<?php

use App\Models\Client;
use App\Models\Meeting;

use function Pest\Laravel\get;

describe('Dashboard Integration', function () {
    beforeEach(function () {
        // Create test data
        $this->client1 = Client::factory()->create(['name' => 'Test Client 1']);
        $this->client2 = Client::factory()->create(['name' => 'Test Client 2']);

        $this->meeting1 = Meeting::factory()->create([
            'client_id' => $this->client1->id,
            'title' => 'Test Meeting 1',
            'status' => 'completed',
        ]);

        $this->meeting2 = Meeting::factory()->create([
            'client_id' => $this->client2->id,
            'title' => 'Test Meeting 2',
            'status' => 'processing',
        ]);

        $this->meeting3 = Meeting::factory()->create([
            'client_id' => $this->client1->id,
            'title' => 'Test Meeting 3',
            'status' => 'pending',
        ]);
    });

    it('displays correct statistics with data', function () {
        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->where('stats.total_clients', 2)
            ->where('stats.total_meetings', 3)
            ->where('stats.completed_meetings', 1)
            ->where('stats.processing_meetings', 1)
            ->where('stats.pending_meetings', 1)
            ->where('stats.failed_meetings', 0)
        );
    });

    it('displays recent meetings with client information', function () {
        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->has('recentMeetings', 3)
            ->has('recentMeetings.0', fn ($meeting) => $meeting->where('title', 'Test Meeting 3')
                ->where('status', 'pending')
                ->has('client', fn ($client) => $client->where('name', 'Test Client 1')
                )
            )
        );
    });

    it('displays top clients with meeting counts', function () {
        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->has('topClients', 2)
            ->has('topClients.0', fn ($client) => $client->where('name', 'Test Client 1')
                ->where('meetings_count', 2)
            )
        );
    });

    it('orders recent meetings by creation date descending', function () {
        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->has('recentMeetings', 3)
            ->where('recentMeetings.0.title', 'Test Meeting 3')
            ->where('recentMeetings.1.title', 'Test Meeting 2')
            ->where('recentMeetings.2.title', 'Test Meeting 1')
        );
    });

    it('orders top clients by meeting count descending', function () {
        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->has('topClients', 2)
            ->where('topClients.0.name', 'Test Client 1')
            ->where('topClients.0.meetings_count', 2)
            ->where('topClients.1.name', 'Test Client 2')
            ->where('topClients.1.meetings_count', 1)
        );
    });

    it('limits recent meetings to 5 items', function () {
        // Create additional meetings
        Meeting::factory()->count(10)->create([
            'client_id' => $this->client1->id,
        ]);

        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->has('recentMeetings', 5)
        );
    });

    it('limits top clients to 5 items', function () {
        // Create additional clients
        Client::factory()->count(10)->create();

        $response = get('/');

        $response->assertInertia(fn ($page) => $page->component('Dashboard')
            ->has('topClients', 5)
        );
    });
});
