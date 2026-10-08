<?php

use App\Models\Meeting;
use App\Models\MeetingShare;
use App\Models\Person;
use App\Models\Transcription;
use App\Models\User;
use Illuminate\Support\Facades\Storage;

it('creates a new persistent public link on every generation without invalidating earlier links', function (): void {
    $meeting = Meeting::factory()->completed()->create();

    $firstUrl = $this->postJson(route('meetings.shares.store', $meeting))->assertCreated()->json('url');
    $secondUrl = $this->postJson(route('meetings.shares.store', $meeting))->assertCreated()->json('url');

    expect($firstUrl)->not->toBe($secondUrl);
    expect($meeting->shares()->count())->toBe(2);

    foreach ($meeting->shares as $share) {
        expect($share->token)->toHaveLength(64)
            ->and($share->expires_at)->toBeNull()
            ->and($share->visits)->toBe(0);
        expect(route('share.show', $share->token))->toContain('/share/'.$share->token);
        $this->get(route('share.show', $share->token))->assertOk();
    }
});

it('shows only the shared meeting content even when the viewer is signed in', function (): void {
    Storage::fake('public');
    $meeting = Meeting::factory()->completed()->create(['technical_error' => 'Private technical information']);
    Storage::disk('public')->put($meeting->video_path, 'video bytes');
    Person::create(['client_id' => $meeting->client_id, 'name' => 'Private contact', 'email' => 'private@example.com']);
    Transcription::factory()->forMeeting($meeting)->create(['start_time' => 20, 'text' => 'Second segment']);
    Transcription::factory()->forMeeting($meeting)->create(['start_time' => 0, 'text' => 'First segment']);
    Meeting::factory()->create(['title' => 'Another private meeting']);
    $share = $meeting->shares()->create(['token' => str_repeat('a', 64)]);

    $this->actingAs(User::factory()->create())->get(route('share.show', $share->token))
        ->assertOk()
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Show')
            ->where('publicShare', true)
            ->where('meeting.title', $meeting->title)
            ->where('meeting.client.name', $meeting->client->name)
            ->where('meeting.transcriptions.0.text', 'First segment')
            ->where('meeting.transcriptions.1.text', 'Second segment')
            ->where('videoUrl', route('share.video', $share->token))
            ->where('statusUrl', route('share.status', $share->token))
            ->missing('meeting.video_path')
            ->missing('meeting.technical_error')
            ->missing('meeting.client.email')
            ->missing('meeting.client.persons')
            ->missing('meeting.transcriptions.0.person_id')
            ->missing('sidebarMeetings')
            ->missing('user')
            ->missing('ziggy'));

    expect($share->fresh()->visits)->toBe(1);
});

it('serves video and status through the token without counting them as visits', function (): void {
    Storage::fake('public');
    $meeting = Meeting::factory()->completed()->create();
    Storage::disk('public')->put($meeting->video_path, 'test video content');
    $share = $meeting->shares()->create(['token' => str_repeat('b', 64)]);

    $this->get(route('share.show', $share->token))->assertOk();
    $this->get(route('share.show', $share->token))->assertOk();
    $this->getJson(route('share.status', $share->token))->assertOk()->assertExactJson(['data' => ['status' => 'completed']]);
    $this->get(route('share.video', $share->token))->assertOk();
    $this->get(route('share.video', $share->token), ['Range' => 'bytes=0-3'])->assertStatus(206);

    expect($share->fresh()->visits)->toBe(2)
        ->and(MeetingShare::count())->toBe(1);
});

it('returns not found for unknown tokens and missing video files', function (): void {
    Storage::fake('public');
    $meeting = Meeting::factory()->completed()->create();
    $share = $meeting->shares()->create(['token' => str_repeat('c', 64)]);

    $this->get('/share/unknown')->assertNotFound();
    $this->get('/share/unknown/video')->assertNotFound();
    $this->get('/share/unknown/status')->assertNotFound();
    $this->get(route('share.video', $share->token))->assertNotFound();
    $this->get(route('share.show', $share->token))->assertInertia(fn ($page) => $page->where('videoUrl', null));
    $this->postJson(route('meetings.shares.store', 999999))->assertNotFound();
});

it('removes shares when their meeting is deleted and exposes no public mutation routes', function (): void {
    $meeting = Meeting::factory()->completed()->create();
    $share = $meeting->shares()->create(['token' => str_repeat('d', 64)]);

    $this->put(route('share.show', $share->token))->assertStatus(405);
    $this->post('/share/'.$share->token.'/people')->assertNotFound();
    $this->put('/share/'.$share->token.'/speakers')->assertNotFound();

    $meeting->delete();

    $this->assertDatabaseMissing('meeting_shares', ['id' => $share->id]);
    $this->get(route('share.show', $share->token))->assertNotFound();
});
