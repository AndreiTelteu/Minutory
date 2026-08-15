<?php

use App\Models\Client;
use App\Models\Meeting;
use App\Models\Person;
use App\Models\Transcription;

it('creates people scoped to a meeting client and exposes them on the meeting screen', function (): void {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->for($client)->create();

    $response = $this->postJson(route('meetings.people.store', $meeting), [
        'name' => 'Ana Popescu',
        'email' => 'ana@example.com',
    ]);

    $response->assertCreated()->assertJsonPath('person.name', 'Ana Popescu');
    $this->assertDatabaseHas('people', [
        'client_id' => $client->id,
        'name' => 'Ana Popescu',
        'email' => 'ana@example.com',
    ]);

    $this->get(route('meetings.show', $meeting))
        ->assertInertia(fn ($page) => $page
            ->component('Meetings/Show')
            ->has('meeting.client.persons', 1)
            ->where('meeting.client.persons.0.name', 'Ana Popescu'));
});

it('renames all selected source labels atomically while preserving unassigned labels', function (): void {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->for($client)->create();
    $person = Person::create(['client_id' => $client->id, 'name' => 'Ana Popescu']);
    $first = Transcription::factory()->forMeeting($meeting)->create(['speaker' => 'SPEAKER_00']);
    $second = Transcription::factory()->forMeeting($meeting)->create(['speaker' => 'SPEAKER_01']);
    $unassigned = Transcription::factory()->forMeeting($meeting)->create(['speaker' => 'SPEAKER_02']);
    $unknown = Transcription::factory()->forMeeting($meeting)->create(['speaker' => null]);

    $this->put(route('meetings.speakers.update', $meeting), [
        'assignments' => [
            ['speaker' => 'SPEAKER_00', 'person_id' => $person->id],
            ['speaker' => 'SPEAKER_01', 'person_id' => $person->id],
            ['speaker' => null, 'person_id' => $person->id],
            ['speaker' => 'SPEAKER_02', 'person_id' => null],
        ],
    ])->assertRedirect();

    foreach ([$first, $second, $unknown] as $transcription) {
        $this->assertDatabaseHas('transcriptions', [
            'id' => $transcription->id,
            'person_id' => $person->id,
            'speaker' => 'Ana Popescu',
        ]);
    }

    $this->assertDatabaseHas('transcriptions', [
        'id' => $unassigned->id,
        'person_id' => null,
        'speaker' => 'SPEAKER_02',
    ]);
});

it('removes an existing person assignment when a detected label is left unassigned', function (): void {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->completed()->for($client)->create();
    $person = Person::create(['client_id' => $client->id, 'name' => 'Ana Popescu']);
    $transcription = Transcription::factory()->forMeeting($meeting)->create([
        'person_id' => $person->id,
        'speaker' => 'Ana Popescu',
    ]);

    $this->put(route('meetings.speakers.update', $meeting), [
        'assignments' => [
            ['speaker' => 'Ana Popescu', 'person_id' => null],
        ],
    ])->assertRedirect();

    $this->assertDatabaseHas('transcriptions', [
        'id' => $transcription->id,
        'person_id' => null,
        'speaker' => 'Ana Popescu',
    ]);
});

it('rejects people belonging to another client without changing any transcription', function (): void {
    $meeting = Meeting::factory()->completed()->create();
    $otherPerson = Person::create(['client_id' => Client::factory()->create()->id, 'name' => 'Other Client Person']);
    $transcription = Transcription::factory()->forMeeting($meeting)->create(['speaker' => 'SPEAKER_00']);

    $this->put(route('meetings.speakers.update', $meeting), [
        'assignments' => [
            ['speaker' => 'SPEAKER_00', 'person_id' => $otherPerson->id],
        ],
    ])->assertSessionHasErrors('assignments');

    $this->assertDatabaseHas('transcriptions', [
        'id' => $transcription->id,
        'person_id' => null,
        'speaker' => 'SPEAKER_00',
    ]);
});

it('does not allow editing speakers until a meeting is completed', function (): void {
    $meeting = Meeting::factory()->processing()->create();
    $person = Person::create(['client_id' => $meeting->client_id, 'name' => 'Ana Popescu']);

    $this->put(route('meetings.speakers.update', $meeting), [
        'assignments' => [['speaker' => 'SPEAKER_00', 'person_id' => $person->id]],
    ])->assertStatus(422);
});
