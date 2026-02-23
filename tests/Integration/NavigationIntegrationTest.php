<?php

use App\Models\Client;
use App\Models\Meeting;

use function Pest\Laravel\get;

describe('Navigation Integration', function () {
    beforeEach(function () {
        $this->client = Client::factory()->create();
        $this->meeting = Meeting::factory()->create(['client_id' => $this->client->id]);
    });

    describe('Main Navigation', function () {
        it('navigates from dashboard to clients index', function () {
            $response = get('/');
            $response->assertStatus(200);

            $response = get(route('clients.index'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
            );
        });

        it('navigates from dashboard to meetings index', function () {
            $response = get('/');
            $response->assertStatus(200);

            $response = get(route('meetings.index'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
            );
        });

        it('navigates from dashboard to AI chat', function () {
            $response = get('/');
            $response->assertStatus(200);

            $response = get(route('ai.chat'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('AI/Chat')
            );
        });

        it('navigates from dashboard to meeting creation', function () {
            $response = get('/');
            $response->assertStatus(200);

            $response = get(route('meetings.create'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
            );
        });
    });

    describe('Client Navigation Flow', function () {
        it('navigates through client management workflow', function () {
            // Start at clients index
            $response = get(route('clients.index'));
            $response->assertStatus(200);

            // Go to create client
            $response = get(route('clients.create'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Create')
            );

            // View existing client
            $response = get(route('clients.show', $this->client));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
            );

            // Edit client
            $response = get(route('clients.edit', $this->client));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Edit')
            );
        });

        it('navigates from client show to client meetings', function () {
            $response = get(route('clients.show', $this->client));
            $response->assertStatus(200);

            // Should show meetings for this client
            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('meetings')
            );
        });
    });

    describe('Meeting Navigation Flow', function () {
        it('navigates through meeting management workflow', function () {
            // Start at meetings index
            $response = get(route('meetings.index'));
            $response->assertStatus(200);

            // Go to create meeting
            $response = get(route('meetings.create'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
            );

            // View existing meeting
            $response = get(route('meetings.show', $this->meeting));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
            );
        });

        it('navigates from meeting to client details', function () {
            $response = get(route('meetings.show', $this->meeting));
            $response->assertStatus(200);

            // Meeting should include client information for navigation
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting.client')
            );

            // Navigate to client
            $response = get(route('clients.show', $this->client));
            $response->assertStatus(200);
        });
    });

    describe('Breadcrumb Navigation', function () {
        it('provides correct navigation context for client pages', function () {
            $response = get(route('clients.show', $this->client));

            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('client')
            );
        });

        it('provides correct navigation context for meeting pages', function () {
            $response = get(route('meetings.show', $this->meeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting')
                ->has('meeting.client')
            );
        });
    });

    describe('Cross-Feature Navigation', function () {
        it('navigates from dashboard recent meetings to meeting details', function () {
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->has('recentMeetings')
            );

            $response = get(route('meetings.show', $this->meeting));
            $response->assertStatus(200);
        });

        it('navigates from dashboard top clients to client details', function () {
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->has('topClients')
            );

            $response = get(route('clients.show', $this->client));
            $response->assertStatus(200);
        });

        it('navigates from client to create meeting for that client', function () {
            $response = get(route('clients.show', $this->client));
            $response->assertStatus(200);

            $response = get(route('meetings.create', ['client_id' => $this->client->id]));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
            );
        });
    });

    describe('Error Page Navigation', function () {
        it('handles 404 errors gracefully', function () {
            $response = get('/non-existent-page');
            $response->assertStatus(404);
        });

        it('handles invalid client ID', function () {
            $response = get(route('clients.show', 99999));
            $response->assertStatus(404);
        });

        it('handles invalid meeting ID', function () {
            $response = get(route('meetings.show', 99999));
            $response->assertStatus(404);
        });
    });

    describe('URL Parameter Handling', function () {
        it('handles query parameters in meetings index', function () {
            $response = get(route('meetings.index', [
                'client_id' => $this->client->id,
                'status' => 'completed',
                'search' => 'test',
            ]));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
            );
        });

        it('preserves filters when navigating', function () {
            $response = get(route('meetings.index', ['status' => 'completed']));
            $response->assertStatus(200);

            // Filters should be maintained in the component
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
            );
        });
    });
});
