<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\Storage;

beforeEach(function () {
    Bus::fake();
    Storage::fake('public');
});

it('stores and normalizes an offset-bearing meeting datetime to UTC', function () {
    $client = Client::factory()->create();

    $this->post(route('meetings.store'), [
        'title' => 'Offset meeting',
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10T13:03:47+03:00',
        'video' => UploadedFile::fake()->create('meeting.mp4', 1024, 'video/mp4'),
    ])->assertRedirect();

    $meeting = Meeting::query()->where('title', 'Offset meeting')->firstOrFail();

    expect($meeting->meeting_at?->utc()->toIso8601String())->toBe('2026-07-10T10:03:47+00:00');
});

it('stores a null meeting datetime', function () {
    $client = Client::factory()->create();

    $this->post(route('meetings.store'), [
        'title' => 'Undated meeting',
        'client_id' => $client->id,
        'meeting_at' => null,
        'video' => UploadedFile::fake()->create('meeting.mp4', 1024, 'video/mp4'),
    ])->assertRedirect();

    expect(Meeting::query()->where('title', 'Undated meeting')->firstOrFail()->meeting_at)->toBeNull();
});

it('updates and clears a meeting datetime', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-01-01 00:00:00',
    ]);

    $this->put(route('meetings.update', $meeting), [
        'title' => 'Updated meeting',
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10T13:03:47-04:00',
    ])->assertRedirect(route('meetings.show', $meeting));

    expect($meeting->fresh()->meeting_at?->utc()->toIso8601String())->toBe('2026-07-10T17:03:47+00:00');

    $this->put(route('meetings.update', $meeting), [
        'title' => 'Updated meeting',
        'client_id' => $client->id,
        'meeting_at' => null,
    ])->assertRedirect(route('meetings.show', $meeting));

    expect($meeting->fresh()->meeting_at)->toBeNull();
});

it('preserves meeting datetime when an older update client omits the field', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'meeting_at' => '2026-07-10 10:03:47',
    ]);

    $this->put(route('meetings.update', $meeting), [
        'title' => 'Legacy update',
        'client_id' => $client->id,
    ])->assertRedirect(route('meetings.show', $meeting));

    expect($meeting->fresh()->meeting_at?->utc()->toIso8601String())->toBe('2026-07-10T10:03:47+00:00');
});

it('strictly rejects invalid web meeting datetimes', function (string $meetingAt) {
    $client = Client::factory()->create();

    $this->put(route('meetings.update', Meeting::factory()->create(['client_id' => $client->id])), [
        'title' => 'Invalid meeting',
        'client_id' => $client->id,
        'meeting_at' => $meetingAt,
    ])->assertSessionHasErrors('meeting_at');
})->with([
    'missing offset' => '2026-07-10T13:03:47',
    'UTC designator instead of numeric browser offset' => '2026-07-10T13:03:47Z',
    'impossible date' => '2026-02-30T13:03:47+03:00',
    'zero year' => '0000-01-01T13:03:47+03:00',
    'year below frontend minimum' => '0999-01-01T13:03:47+03:00',
    'impossible time' => '2026-07-10T24:03:47+03:00',
    'offset out of range' => '2026-07-10T13:03:47+15:00',
    'minutes beyond the maximum offset' => '2026-07-10T13:03:47+14:30',
    'missing seconds' => '2026-07-10T13:03+03:00',
]);

it('accepts the aligned minimum meeting year', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create(['client_id' => $client->id]);

    $this->put(route('meetings.update', $meeting), [
        'title' => 'Year one thousand',
        'client_id' => $client->id,
        'meeting_at' => '1000-01-02T03:04:05+00:00',
    ])->assertRedirect(route('meetings.show', $meeting));

    expect($meeting->fresh()->meeting_at?->utc()->format('Y-m-d\\TH:i:sP'))->toBe('1000-01-02T03:04:05+00:00');
});

it('exposes meeting and upload times on index and show props for a metadata-only meeting', function () {
    $meeting = Meeting::factory()->create([
        'meeting_at' => '2026-07-10 10:03:47',
        'uploaded_at' => '2026-07-11 09:00:00',
        'video_path' => null,
    ]);

    $this->get(route('meetings.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Index')
            ->where('meetings.data.0.id', $meeting->id)
            ->has('meetings.data.0.meeting_at')
            ->has('meetings.data.0.uploaded_at')
        );

    $this->get(route('meetings.show', $meeting))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Show')
            ->where('meeting.id', $meeting->id)
            ->has('meeting.meeting_at')
            ->has('meeting.uploaded_at')
            ->where('videoUrl', null)
            ->where('videoError', 'No video file associated with this meeting.')
        );
});

it('exposes null meeting and upload timestamps without requiring a video', function () {
    $meeting = Meeting::factory()->create([
        'meeting_at' => null,
        'uploaded_at' => null,
        'video_path' => null,
    ]);

    $this->get(route('meetings.index'))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Index')
            ->where('meetings.data.0.id', $meeting->id)
            ->where('meetings.data.0.meeting_at', null)
            ->where('meetings.data.0.uploaded_at', null)
        );

    $this->get(route('meetings.show', $meeting))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Show')
            ->where('meeting.id', $meeting->id)
            ->where('meeting.meeting_at', null)
            ->where('meeting.uploaded_at', null)
            ->where('videoUrl', null)
        );
});
