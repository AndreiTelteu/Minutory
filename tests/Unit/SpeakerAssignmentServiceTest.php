<?php

uses(Tests\TestCase::class, Illuminate\Foundation\Testing\RefreshDatabase::class);

use App\Models\Meeting;
use App\Models\Transcription;
use App\Services\SpeakerAssignmentService;

it('assigns the speaker with the largest overlap and keeps uncovered labels', function (): void {
    $meeting = Meeting::factory()->create();
    $dominant = Transcription::factory()->forMeeting($meeting)->create([
        'start_time' => 10.0,
        'end_time' => 20.0,
        'speaker' => null,
    ]);
    $uncovered = Transcription::factory()->forMeeting($meeting)->create([
        'start_time' => 30.0,
        'end_time' => 35.0,
        'speaker' => 'Existing speaker',
    ]);

    $updated = app(SpeakerAssignmentService::class)->apply($meeting, [
        ['start' => 10.0, 'end' => 14.0, 'speaker' => 'Speaker B'],
        ['start' => 14.0, 'end' => 20.0, 'speaker' => 'Speaker A'],
    ]);

    expect($updated)->toBe(1)
        ->and($dominant->fresh()->speaker)->toBe('Speaker A')
        ->and($uncovered->fresh()->speaker)->toBe('Existing speaker');
});

it('breaks equal overlap ties by speaker label deterministically', function (): void {
    $meeting = Meeting::factory()->create();
    $segment = Transcription::factory()->forMeeting($meeting)->create([
        'start_time' => 10.0,
        'end_time' => 20.0,
        'speaker' => null,
    ]);

    app(SpeakerAssignmentService::class)->apply($meeting, [
        ['start' => 15.0, 'end' => 20.0, 'speaker' => 'Speaker B'],
        ['start' => 10.0, 'end' => 15.0, 'speaker' => 'Speaker A'],
    ]);

    expect($segment->fresh()->speaker)->toBe('Speaker A');
});
