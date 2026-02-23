<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;

use function Pest\Laravel\delete;
use function Pest\Laravel\get;
use function Pest\Laravel\post;

describe('Meeting UI Integration', function () {
    beforeEach(function () {
        Storage::fake('public');

        $this->client = Client::factory()->create([
            'name' => 'Test Client',
        ]);

        $this->meeting = Meeting::factory()->create([
            'client_id' => $this->client->id,
            'title' => 'Test Meeting',
            'status' => 'completed',
            'transcript' => 'This is a test transcript.',
            'summary' => 'This is a test summary.',
            'action_items' => ['Action 1', 'Action 2'],
        ]);
    });

    describe('Meeting Index Page', function () {
        it('displays meetings index page', function () {
            $response = get(route('meetings.index'));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings')
                ->has('clients')
            );
        });

        it('displays meeting data with client information', function () {
            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->has('meetings.data.0', fn ($meeting) => $meeting->where('title', 'Test Meeting')
                    ->where('status', 'completed')
                    ->has('client', fn ($client) => $client->where('name', 'Test Client')
                    )
                )
            );
        });

        it('provides clients for filtering', function () {
            $response = get(route('meetings.index'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('clients', 1)
                ->has('clients.0', fn ($client) => $client->where('name', 'Test Client')
                )
            );
        });

        it('filters meetings by client', function () {
            $otherClient = Client::factory()->create(['name' => 'Other Client']);
            Meeting::factory()->create([
                'client_id' => $otherClient->id,
                'title' => 'Other Meeting',
            ]);

            $response = get(route('meetings.index', ['client_id' => $this->client->id]));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->where('meetings.data.0.title', 'Test Meeting')
            );
        });

        it('filters meetings by status', function () {
            Meeting::factory()->create([
                'client_id' => $this->client->id,
                'title' => 'Pending Meeting',
                'status' => 'pending',
            ]);

            $response = get(route('meetings.index', ['status' => 'completed']));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->where('meetings.data.0.title', 'Test Meeting')
            );
        });

        it('searches meetings by title', function () {
            Meeting::factory()->create([
                'client_id' => $this->client->id,
                'title' => 'Different Meeting',
            ]);

            $response = get(route('meetings.index', ['search' => 'Test']));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Index')
                ->has('meetings.data', 1)
                ->where('meetings.data.0.title', 'Test Meeting')
            );
        });
    });

    describe('Meeting Show Page', function () {
        it('displays meeting show page', function () {
            $response = get(route('meetings.show', $this->meeting));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting')
            );
        });

        it('displays meeting details with client', function () {
            $response = get(route('meetings.show', $this->meeting));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('title', 'Test Meeting')
                    ->where('status', 'completed')
                    ->where('transcript', 'This is a test transcript.')
                    ->where('summary', 'This is a test summary.')
                    ->where('action_items', ['Action 1', 'Action 2'])
                    ->has('client', fn ($client) => $client->where('name', 'Test Client')
                    )
                )
            );
        });

        it('handles meeting without transcript', function () {
            $pendingMeeting = Meeting::factory()->create([
                'client_id' => $this->client->id,
                'status' => 'pending',
                'transcript' => null,
                'summary' => null,
                'action_items' => null,
            ]);

            $response = get(route('meetings.show', $pendingMeeting));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Show')
                ->has('meeting', fn ($meeting) => $meeting->where('status', 'pending')
                    ->where('transcript', null)
                    ->where('summary', null)
                    ->where('action_items', null)
                )
            );
        });
    });

    describe('Meeting Create Page', function () {
        it('displays meeting create page', function () {
            $response = get(route('meetings.create'));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
                ->has('clients')
            );
        });

        it('provides clients for selection', function () {
            $response = get(route('meetings.create'));

            $response->assertInertia(fn ($page) => $page->component('Meetings/Create')
                ->has('clients', 1)
                ->has('clients.0', fn ($client) => $client->where('name', 'Test Client')
                )
            );
        });

        it('creates meeting with file upload', function () {
            $file = UploadedFile::fake()->create('meeting.mp4', 1000, 'video/mp4');

            $meetingData = [
                'title' => 'New Meeting',
                'client_id' => $this->client->id,
                'file' => $file,
            ];

            $response = post(route('meetings.store'), $meetingData);

            $response->assertRedirect();
            $this->assertDatabaseHas('meetings', [
                'title' => 'New Meeting',
                'client_id' => $this->client->id,
                'status' => 'pending',
            ]);

            Storage::disk('public')->assertExists('meetings/'.$file->hashName());
        });

        it('validates required fields', function () {
            $response = post(route('meetings.store'), []);

            $response->assertSessionHasErrors(['title', 'client_id', 'file']);
        });

        it('validates file type', function () {
            $file = UploadedFile::fake()->create('document.pdf', 1000, 'application/pdf');

            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => $this->client->id,
                'file' => $file,
            ]);

            $response->assertSessionHasErrors(['file']);
        });

        it('validates file size', function () {
            $file = UploadedFile::fake()->create('large.mp4', 1000000, 'video/mp4'); // 1GB

            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => $this->client->id,
                'file' => $file,
            ]);

            $response->assertSessionHasErrors(['file']);
        });
    });

    describe('Meeting Status API', function () {
        it('returns meeting status', function () {
            $response = get(route('meetings.status', $this->meeting));

            $response->assertStatus(200);
            $response->assertJson([
                'status' => 'completed',
            ]);
        });

        it('returns updated status for processing meeting', function () {
            $processingMeeting = Meeting::factory()->create([
                'client_id' => $this->client->id,
                'status' => 'processing',
            ]);

            $response = get(route('meetings.status', $processingMeeting));

            $response->assertStatus(200);
            $response->assertJson([
                'status' => 'processing',
            ]);
        });
    });

    describe('Meeting Delete', function () {
        it('deletes meeting successfully', function () {
            $response = delete(route('meetings.destroy', $this->meeting));

            $response->assertRedirect(route('meetings.index'));
            $this->assertDatabaseMissing('meetings', ['id' => $this->meeting->id]);
        });

        it('deletes associated files', function () {
            $this->meeting->update(['file_path' => 'meetings/test-file.mp4']);
            Storage::disk('public')->put('meetings/test-file.mp4', 'test content');

            $response = delete(route('meetings.destroy', $this->meeting));

            $response->assertRedirect(route('meetings.index'));
            Storage::disk('public')->assertMissing('meetings/test-file.mp4');
        });
    });
});
