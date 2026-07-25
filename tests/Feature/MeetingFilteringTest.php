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
    $firstNull = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => null,
    ]);
    $secondNull = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => null,
    ]);

    $this->get(route('meetings.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->where('meetings.data.0.id', $newest->id)
            ->where('meetings.data.1.id', $fallback->id)
            ->where('meetings.data.2.id', $oldest->id)
            ->where('meetings.data.3.id', $secondNull->id)
            ->where('meetings.data.4.id', $firstNull->id)
        );

    $this->get(route('meetings.index', ['sort' => 'meeting_at', 'direction' => 'asc']))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->where('filters.sort', 'meeting_at')
            ->where('filters.direction', 'asc')
            ->where('meetings.data.0.id', $oldest->id)
            ->where('meetings.data.1.id', $fallback->id)
            ->where('meetings.data.2.id', $newest->id)
            ->where('meetings.data.3.id', $secondNull->id)
            ->where('meetings.data.4.id', $firstNull->id)
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

it('filters Europe Bucharest calendar-day boundaries and uploaded time fallback as UTC instants', function () {
    $client = Client::factory()->create();
    $start = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-09 21:00:00',
        'uploaded_at' => null,
    ]);
    $end = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 20:59:59',
        'uploaded_at' => null,
    ]);
    $fallback = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => '2026-07-10 10:00:00',
    ]);
    Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-09 20:59:59',
    ]);
    Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 21:00:00',
    ]);

    $this->get(route('meetings.index', [
        'date_from' => '2026-07-10',
        'date_to' => '2026-07-10',
        'timezone' => 'Europe/Bucharest',
    ]))->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 3)
            ->where('meetings.data.0.id', $end->id)
            ->where('meetings.data.1.id', $fallback->id)
            ->where('meetings.data.2.id', $start->id)
            ->where('filters.timezone', 'Europe/Bucharest')
        );
});

it('filters negative-offset local calendar boundaries', function () {
    $client = Client::factory()->create();
    $included = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 07:00:00',
    ]);
    Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 06:59:59',
    ]);
    Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-11 07:00:00',
    ]);

    $this->get(route('meetings.index', [
        'date_from' => '2026-07-10',
        'date_to' => '2026-07-10',
        'timezone' => 'America/Los_Angeles',
    ]))->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 1)
            ->where('meetings.data.0.id', $included->id)
        );
});

it('uses the correct shortened UTC range on a DST transition day', function () {
    $client = Client::factory()->create();
    $start = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-03-28 22:00:00',
    ]);
    $end = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-03-29 20:59:59',
    ]);
    Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-03-28 21:59:59',
    ]);
    Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-03-29 21:00:00',
    ]);

    $this->get(route('meetings.index', [
        'date_from' => '2026-03-29',
        'date_to' => '2026-03-29',
        'timezone' => 'Europe/Bucharest',
    ]))->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 2)
            ->where('meetings.data.0.id', $end->id)
            ->where('meetings.data.1.id', $start->id)
        );
});

it('rejects malformed meeting index filters with a controlled redirect', function (array $query, string $field) {
    $this->from(route('meetings.index'))
        ->get(route('meetings.index', $query))
        ->assertRedirect(route('meetings.index'))
        ->assertSessionHasErrors($field);
})->with([
    'array date from' => [['date_from' => ['2026-07-10']], 'date_from'],
    'malformed date' => [['date_from' => '10/07/2026'], 'date_from'],
    'impossible date' => [['date_to' => '2026-02-30'], 'date_to'],
    'reversed range' => [['date_from' => '2026-07-11', 'date_to' => '2026-07-10'], 'date_to'],
    'array timezone' => [['timezone' => ['Europe/Bucharest']], 'timezone'],
    'invalid timezone' => [['timezone' => 'Mars/Olympus'], 'timezone'],
    'array sort' => [['sort' => ['meeting_at']], 'sort'],
    'invalid sort' => [['sort' => 'created_at'], 'sort'],
    'array direction' => [['direction' => ['desc']], 'direction'],
    'invalid direction' => [['direction' => 'sideways'], 'direction'],
]);

it('keeps meetings with both timestamps null ordered and paginated deterministically', function () {
    $client = Client::factory()->create();

    for ($day = 1; $day <= 15; $day++) {
        Meeting::factory()->create([
            'client_id' => $client->id,
            'meeting_at' => sprintf('2026-07-%02d 10:00:00', $day),
            'uploaded_at' => null,
        ]);
    }

    $firstNull = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => null,
    ]);
    $secondNull = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => null,
        'uploaded_at' => null,
    ]);

    $this->get(route('meetings.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 15)
            ->where('meetings.total', 17)
            ->where('meetings.current_page', 1)
        );

    $this->get(route('meetings.index', ['page' => 2]))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->has('meetings.data', 2)
            ->where('meetings.current_page', 2)
            ->where('meetings.data.0.id', $secondNull->id)
            ->where('meetings.data.1.id', $firstNull->id)
        );
});
