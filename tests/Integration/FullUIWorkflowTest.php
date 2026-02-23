<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;

use function Pest\Laravel\delete;
use function Pest\Laravel\get;
use function Pest\Laravel\post;
use function Pest\Laravel\put;

describe('Full UI Workflow Integration', function () {
    beforeEach(function () {
        Storage::fake('public');
    });

    describe('Complete Client Management Workflow', function () {
        it('completes full client lifecycle', function () {
            // 1. Start at dashboard
            $response = get('/');
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_clients', 0)
            );

            // 2. Navigate to clients index
            $response = get(route('clients.index'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.data', 0)
            );

            // 3. Create new client
            $response = get(route('clients.create'));
            $response->assertStatus(200);

            $clientData = [
                'name' => 'Test Client',
                'email' => 'test@example.com',
                'phone' => '123-456-7890',
                'company' => 'Test Company',
            ];

            $response = post(route('clients.store'), $clientData);
            $response->assertRedirect(route('clients.index'));

            // 4. Verify client appears in index
            $response = get(route('clients.index'));
            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.data', 1)
                ->has('clients.data.0', fn ($client) => $client->where('name', 'Test Client')
                )
            );

            $client = Client::where('email', 'test@example.com')->first();

            // 5. View client details
            $response = get(route('clients.show', $client));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('client', fn ($client) => $client->where('name', 'Test Client')
                )
            );

            // 6. Edit client
            $response = get(route('clients.edit', $client));
            $response->assertStatus(200);

            $updateData = [
                'name' => 'Updated Client',
                'email' => 'test@example.com',
                'phone' => '987-654-3210',
                'company' => 'Updated Company',
            ];

            $response = put(route('clients.update', $client), $updateData);
            $response->assertRedirect(route('clients.show', $client));

            // 7. Verify update
            $response = get(route('clients.show', $client));
            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('client', fn ($client) => $client->where('name', 'Updated Client')
                )
            );

            // 8. Verify dashboard reflects changes
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_clients', 1)
            );
        });
    });

    describe('Complete Meeting Management Workflow', function () {
        it('completes full meeting lifecycle', function () {
            // Setup: Create a client first
            $client = Client::factory()->create(['name' => 'Test Client']);

            // 1. Start at dashboard
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_meetings', 0)
            );

            // 2. Navigate to meetings index
            $response = get(route('meetings.index'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 0)
            );

            // 3. Create new meeting
            $response = get(route('meetings.create'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
                ->has('clients', 1)
            );

            $file = UploadedFile::fake()->create('meeting.mp4', 1000, 'video/mp4');
            $meetingData = [
                'title' => 'Test Meeting',
                'client_id' => $client->id,
                'file' => $file,
            ];

            $response = post(route('meetings.store'), $meetingData);
            $response->assertRedirect();

            // 4. Verify meeting appears in index
            $response = get(route('meetings.index'));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->has('meetings.data.0', fn ($meeting) => $meeting->where('title', 'Test Meeting')
                    ->where('status', 'pending')
                )
            );

            $meeting = Meeting::where('title', 'Test Meeting')->first();

            // 5. View meeting details
            $response = get(route('meetings.show', $meeting));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('title', 'Test Meeting')
                    ->where('status', 'pending')
                )
            );

            // 6. Simulate processing completion
            $meeting->update([
                'status' => 'completed',
                'transcript' => 'This is a test transcript.',
                'summary' => 'This is a test summary.',
                'action_items' => ['Action 1', 'Action 2'],
            ]);

            // 7. View completed meeting
            $response = get(route('meetings.show', $meeting));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'completed')
                    ->where('transcript', 'This is a test transcript.')
                    ->where('summary', 'This is a test summary.')
                )
            );

            // 8. Verify dashboard reflects changes
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_meetings', 1)
                ->where('stats.completed_meetings', 1)
                ->has('recentMeetings', 1)
            );

            // 9. Delete meeting
            $response = delete(route('meetings.destroy', $meeting));
            $response->assertRedirect(route('meetings.index'));

            // 10. Verify deletion
            $response = get(route('meetings.index'));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 0)
            );
        });
    });

    describe('Cross-Feature Integration Workflow', function () {
        it('demonstrates integration between all features', function () {
            // 1. Create client
            $clientData = [
                'name' => 'Integration Client',
                'email' => 'integration@example.com',
                'company' => 'Integration Corp',
            ];
            $response = post(route('clients.store'), $clientData);
            $client = Client::where('email', 'integration@example.com')->first();

            // 2. Create multiple meetings for the client
            $file1 = UploadedFile::fake()->create('meeting1.mp4', 1000, 'video/mp4');
            $file2 = UploadedFile::fake()->create('meeting2.mp4', 1000, 'video/mp4');

            post(route('meetings.store'), [
                'title' => 'First Meeting',
                'client_id' => $client->id,
                'file' => $file1,
            ]);

            post(route('meetings.store'), [
                'title' => 'Second Meeting',
                'client_id' => $client->id,
                'file' => $file2,
            ]);

            // 3. Complete one meeting
            $meeting1 = Meeting::where('title', 'First Meeting')->first();
            $meeting1->update([
                'status' => 'completed',
                'transcript' => 'First meeting transcript about project planning.',
                'summary' => 'Discussed project timeline and deliverables.',
                'action_items' => ['Create project plan', 'Schedule follow-up'],
            ]);

            // 4. Verify dashboard shows correct stats
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_clients', 1)
                ->where('stats.total_meetings', 2)
                ->where('stats.completed_meetings', 1)
                ->where('stats.pending_meetings', 1)
                ->has('recentMeetings', 2)
                ->has('topClients', 1)
                ->has('topClients.0', fn ($client) => $client->where('meetings_count', 2)
                )
            );

            // 5. Filter meetings by client
            $response = get(route('meetings.index', ['client_id' => $client->id]));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 2)
            );

            // 6. Filter meetings by status
            $response = get(route('meetings.index', ['status' => 'completed']));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->where('meetings.data.0.title', 'First Meeting')
            );

            // 7. Search meetings
            $response = get(route('meetings.index', ['search' => 'First']));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->where('meetings.data.0.title', 'First Meeting')
            );

            // 8. View client with meetings
            $response = get(route('clients.show', $client));
            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('meetings.data', 2)
            );

            // 9. Navigate from dashboard to meeting details
            $response = get(route('meetings.show', $meeting1));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('title', 'First Meeting')
                    ->has('client', fn ($client) => $client->where('name', 'Integration Client')
                    )
                )
            );

            // 10. Test AI integration (if available)
            $response = get(route('ai.chat'));
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('AI/Chat')
            );
        });
    });

    describe('Error Recovery Workflow', function () {
        it('handles errors gracefully throughout workflow', function () {
            // 1. Try to create client with invalid data
            $response = post(route('clients.store'), [
                'name' => '',
                'email' => 'invalid-email',
            ]);
            $response->assertSessionHasErrors(['name', 'email']);

            // 2. Create valid client
            $clientData = [
                'name' => 'Error Test Client',
                'email' => 'error@example.com',
            ];
            $response = post(route('clients.store'), $clientData);
            $client = Client::where('email', 'error@example.com')->first();

            // 3. Try to create meeting with invalid file
            $invalidFile = UploadedFile::fake()->create('document.pdf', 1000, 'application/pdf');
            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => $client->id,
                'file' => $invalidFile,
            ]);
            $response->assertSessionHasErrors(['file']);

            // 4. Create valid meeting
            $validFile = UploadedFile::fake()->create('meeting.mp4', 1000, 'video/mp4');
            $response = post(route('meetings.store'), [
                'title' => 'Valid Meeting',
                'client_id' => $client->id,
                'file' => $validFile,
            ]);
            $meeting = Meeting::where('title', 'Valid Meeting')->first();

            // 5. Try to delete client with meetings
            $response = delete(route('clients.destroy', $client));
            $response->assertSessionHasErrors();
            $this->assertDatabaseHas('clients', ['id' => $client->id]);

            // 6. Delete meeting first, then client
            $response = delete(route('meetings.destroy', $meeting));
            $response->assertRedirect(route('meetings.index'));

            $response = delete(route('clients.destroy', $client));
            $response->assertRedirect(route('clients.index'));

            // 7. Verify everything is cleaned up
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_clients', 0)
                ->where('stats.total_meetings', 0)
            );
        });
    });

    describe('Performance and Pagination Workflow', function () {
        it('handles large datasets efficiently', function () {
            // 1. Create multiple clients
            $clients = Client::factory()->count(25)->create();

            // 2. Create meetings for each client
            foreach ($clients->take(10) as $client) {
                Meeting::factory()->count(3)->create(['client_id' => $client->id]);
            }

            // 3. Test pagination on clients index
            $response = get(route('clients.index'));
            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.links')
                ->has('clients.meta')
            );

            // 4. Test pagination on meetings index
            $response = get(route('meetings.index'));
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.links')
                ->has('meetings.meta')
            );

            // 5. Test dashboard with large dataset
            $response = get('/');
            $response->assertInertia(fn ($page) => $page->component('Dashboard')
                ->where('stats.total_clients', 25)
                ->where('stats.total_meetings', 30)
                ->has('recentMeetings', 5) // Limited to 5
                ->has('topClients', 5) // Limited to 5
            );

            // 6. Test filtering with large dataset
            $firstClient = $clients->first();
            $response = get(route('meetings.index', ['client_id' => $firstClient->id]));
            $response->assertStatus(200);

            // 7. Test search with large dataset
            $response = get(route('meetings.index', ['search' => 'test']));
            $response->assertStatus(200);
        });
    });
});
