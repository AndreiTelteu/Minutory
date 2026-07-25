<?php

use App\Models\Client;
use App\Models\Meeting;

it('can filter meetings by status via HTTP request', function () {
    $client = Client::factory()->create();

    $pendingMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Pending Meeting',
        'status' => 'pending',
    ]);

    $completedMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Completed Meeting',
        'status' => 'completed',
    ]);

    $response = $this->get('/meetings?status=pending');

    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 1)
            ->where('meetings.data.0.id', $pendingMeeting->id)
        );
});

it('can filter meetings by client via HTTP request', function () {
    $client1 = Client::factory()->create(['name' => 'Client 1']);
    $client2 = Client::factory()->create(['name' => 'Client 2']);

    $meeting1 = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Client 1 Meeting',
    ]);

    $meeting2 = Meeting::factory()->create([
        'client_id' => $client2->id,
        'title' => 'Client 2 Meeting',
    ]);

    $response = $this->get("/meetings?client_id={$client1->id}");

    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 1)
            ->where('meetings.data.0.id', $meeting1->id)
        );
});

it('can filter meetings by date range via HTTP request', function () {
    $client = Client::factory()->create();

    $oldMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Old Meeting',
        'uploaded_at' => now()->subDays(10),
    ]);

    $recentMeeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Recent Meeting',
        'uploaded_at' => now()->subDays(1),
    ]);

    $dateFrom = now()->subDays(2)->format('Y-m-d');
    $response = $this->get("/meetings?date_from={$dateFrom}");

    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 1)
            ->where('meetings.data.0.id', $recentMeeting->id)
        );
});

it('can combine multiple filters', function () {
    $client1 = Client::factory()->create(['name' => 'Client 1']);
    $client2 = Client::factory()->create(['name' => 'Client 2']);

    $targetMeeting = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Target Meeting',
        'status' => 'completed',
        'uploaded_at' => now()->subDays(1),
    ]);

    $wrongClientMeeting = Meeting::factory()->create([
        'client_id' => $client2->id,
        'title' => 'Wrong Client Meeting',
        'status' => 'completed',
        'uploaded_at' => now()->subDays(1),
    ]);

    $wrongStatusMeeting = Meeting::factory()->create([
        'client_id' => $client1->id,
        'title' => 'Wrong Status Meeting',
        'status' => 'pending',
        'uploaded_at' => now()->subDays(1),
    ]);

    $dateFrom = now()->subDays(2)->format('Y-m-d');
    $response = $this->get("/meetings?client_id={$client1->id}&status=completed&date_from={$dateFrom}");

    $response->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 1)
            ->where('meetings.data.0.id', $targetMeeting->id)
        );
});

it('filters by effective meeting time with upload time as the null fallback', function () {
    $client = Client::factory()->create();

    $includedByMeetingTime = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Included by meeting time',
        'meeting_at' => '2026-07-10 12:00:00',
        'uploaded_at' => '2026-06-01 12:00:00',
    ]);
    $includedByUploadFallback = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Included by upload fallback',
        'meeting_at' => null,
        'uploaded_at' => '2026-07-10 18:00:00',
    ]);
    $excludedDespiteRecentUpload = Meeting::factory()->create([
        'client_id' => $client->id,
        'title' => 'Excluded despite recent upload',
        'meeting_at' => '2026-06-01 12:00:00',
        'uploaded_at' => '2026-07-10 18:00:00',
    ]);

    $this->get(route('meetings.index', [
        'date_from' => '2026-07-10',
        'date_to' => '2026-07-10',
    ]))->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Index')
            ->has('meetings.data', 2)
            ->where('meetings.data.0.id', $includedByUploadFallback->id)
            ->where('meetings.data.1.id', $includedByMeetingTime->id)
        );

    expect($excludedDespiteRecentUpload->exists)->toBeTrue();
});

it('sorts deterministically by effective meeting time and falls back for null meeting dates', function () {
    $client = Client::factory()->create();

    $oldest = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-08 10:00:00',
        'uploaded_at' => '2026-07-20 10:00:00',
    ]);
    $fallback = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => '2026-07-09 10:00:00',
    ]);
    $newest = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 10:00:00',
        'uploaded_at' => '2026-07-01 10:00:00',
    ]);

    $this->get(route('meetings.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->where('meetings.data.0.id', $newest->id)
            ->where('meetings.data.1.id', $fallback->id)
            ->where('meetings.data.2.id', $oldest->id)
        );

    $this->get(route('meetings.index', ['sort' => 'meeting_at', 'direction' => 'asc']))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->where('filters.sort', 'meeting_at')
            ->where('filters.direction', 'asc')
            ->where('meetings.data.0.id', $oldest->id)
            ->where('meetings.data.1.id', $fallback->id)
            ->where('meetings.data.2.id', $newest->id)
        );
});

it('uses descending ids to break effective meeting time ties', function () {
    $client = Client::factory()->create();
    $first = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => '2026-07-10 10:00:00',
    ]);
    $second = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 10:00:00',
        'uploaded_at' => '2026-07-01 10:00:00',
    ]);

    $this->get(route('meetings.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->where('meetings.data.0.id', $second->id)
            ->where('meetings.data.1.id', $first->id)
        );
});
