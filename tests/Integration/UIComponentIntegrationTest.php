<?php

use App\Models\Client;
use App\Models\Meeting;

use function Pest\Laravel\get;

describe('UI Component Integration', function () {
    beforeEach(function () {
        $this->client = Client::factory()->create(['name' => 'Test Client']);
        $this->completedMeeting = Meeting::factory()->create([
            'client_id' => $this->client->id,
            'title' => 'Completed Meeting',
            'status' => 'completed',
        ]);
        $this->processingMeeting = Meeting::factory()->create([
            'client_id' => $this->client->id,
            'title' => 'Processing Meeting',
            'status' => 'processing',
        ]);
        $this->pendingMeeting = Meeting::factory()->create([
            'client_id' => $this->client->id,
            'title' => 'Pending Meeting',
            'status' => 'pending',
        ]);
        $this->failedMeeting = Meeting::factory()->create([
            'client_id' => $this->client->id,
            'title' => 'Failed Meeting',
            'status' => 'failed',
        ]);
    });

    describe('Meeting Status Badge Component', function () {
        it('displays correct status for completed meeting', function () {
            $response = get(route('meetings.show', $this->completedMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'completed')
                )
            );
        });

        it('displays correct status for processing meeting', function () {
            $response = get(route('meetings.show', $this->processingMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'processing')
                )
            );
        });

        it('displays correct status for pending meeting', function () {
            $response = get(route('meetings.show', $this->pendingMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'pending')
                )
            );
        });

        it('displays correct status for failed meeting', function () {
            $response = get(route('meetings.show', $this->failedMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'failed')
                )
            );
        });

        it('shows status badges in meetings index', function () {
            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 4)
                ->has('meetings.data.0', fn ($meeting) => $meeting->where('status', fn ($s) => in_array($s, ['completed', 'processing', 'pending', 'failed'], true))
                )
            );
        });
    });

    describe('Pagination Component', function () {
        it('displays pagination for clients when needed', function () {
            Client::factory()->count(20)->create();

            $response = get(route('clients.index'));

            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.links')
                ->has('clients.meta')
            );
        });

        it('displays pagination for meetings when needed', function () {
            Meeting::factory()->count(20)->create(['client_id' => $this->client->id]);

            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.links')
                ->has('meetings.meta')
            );
        });

        it('handles pagination navigation', function () {
            Meeting::factory()->count(20)->create(['client_id' => $this->client->id]);

            $response = get(route('meetings.index', ['page' => 2]));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
            );
        });
    });

    describe('Search and Filter Components', function () {
        it('displays search functionality in meetings index', function () {
            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('clients') // For client filter dropdown
            );
        });

        it('maintains search state in URL', function () {
            $response = get(route('meetings.index', ['search' => 'test query']));

            $response->assertStatus(200);
        });

        it('maintains filter state in URL', function () {
            $response = get(route('meetings.index', [
                'client_id' => $this->client->id,
                'status' => 'completed',
            ]));

            $response->assertStatus(200);
        });
    });

    describe('Form Components', function () {
        it('displays client form with validation', function () {
            $response = get(route('clients.create'));

            $response->assertInertia(fn ($page) => $page->component('Clients/Create')
            );
        });

        it('displays meeting upload form with client selection', function () {
            $response = get(route('meetings.create'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
                ->has('clients')
            );
        });

        it('pre-populates edit forms with existing data', function () {
            $response = get(route('clients.edit', $this->client));

            $response->assertInertia(fn ($page) => $page->component('Clients/Edit')
                ->has('client', fn ($client) => $client->where('name', 'Test Client')
                )
            );
        });
    });

    describe('Data Display Components', function () {
        it('displays meeting transcript when available', function () {
            $this->completedMeeting->update([
                'transcript' => 'This is a test transcript content.',
            ]);

            $response = get(route('meetings.show', $this->completedMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('transcript', 'This is a test transcript content.')
                )
            );
        });

        it('displays meeting summary when available', function () {
            $this->completedMeeting->update([
                'summary' => 'This is a test summary.',
            ]);

            $response = get(route('meetings.show', $this->completedMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('summary', 'This is a test summary.')
                )
            );
        });

        it('displays action items when available', function () {
            $this->completedMeeting->update([
                'action_items' => ['Action 1', 'Action 2', 'Action 3'],
            ]);

            $response = get(route('meetings.show', $this->completedMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('action_items', ['Action 1', 'Action 2', 'Action 3'])
                )
            );
        });

        it('handles empty states gracefully', function () {
            $response = get(route('meetings.show', $this->pendingMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('transcript', null)
                    ->where('summary', null)
                    ->where('action_items', null)
                )
            );
        });
    });

    describe('Interactive Components', function () {
        it('provides interactive elements for meeting management', function () {
            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings')
                ->has('clients')
            );
        });

        it('provides interactive elements for client management', function () {
            $response = get(route('clients.index'));

            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients')
            );
        });

        it('provides navigation elements in dashboard', function () {
            $response = get('/');

            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->has('recentMeetings')
                ->has('stats')
                ->has('topClients')
            );
        });
    });

    describe('Responsive Design Components', function () {
        it('provides data structure for responsive tables', function () {
            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data')
            );
        });

        it('provides data structure for responsive cards', function () {
            $response = get('/');

            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->has('stats')
            );
        });
    });

    describe('Loading States', function () {
        it('provides data for loading state management', function () {
            $response = get(route('meetings.show', $this->processingMeeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'processing')
                )
            );
        });

        it('handles real-time status updates', function () {
            $response = get(route('meetings.status', $this->processingMeeting));

            $response->assertStatus(200);
            $response->assertJson([
                'status' => 'processing',
            ]);
        });
    });
});
