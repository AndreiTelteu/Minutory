<?php

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Contracts\Queue\ShouldBeUnique;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\DB;

it('queues failed and pending meetings', function () {
    Bus::fake();

    $client = Client::factory()->create();
    $pending = Meeting::query()->create([
        'client_id' => $client->id,
        'title' => 'Pending meeting',
        'video_path' => 'meetings/pending/video.mp4',
        'status' => 'pending',
    ]);
    $failed = Meeting::query()->create([
        'client_id' => $client->id,
        'title' => 'Failed meeting',
        'video_path' => 'meetings/failed/video.mp4',
        'status' => 'failed',
        'error_message' => 'Old runtime error',
        'technical_error' => 'python not found',
    ]);
    $processing = Meeting::query()->create([
        'client_id' => $client->id,
        'title' => 'Processing meeting',
        'video_path' => 'meetings/processing/video.mp4',
        'status' => 'processing',
    ]);
    $completed = Meeting::query()->create([
        'client_id' => $client->id,
        'title' => 'Completed meeting',
        'video_path' => 'meetings/completed/video.mp4',
        'status' => 'completed',
    ]);

    $this->artisan('app:process-meetings')
        ->expectsOutput("Queued meeting {$pending->id}: {$pending->title}")
        ->expectsOutput("Queued meeting {$failed->id}: {$failed->title}")
        ->assertSuccessful();

    Bus::assertDispatched(TranscribeMeetingJob::class, fn (TranscribeMeetingJob $job) => $job->meeting->is($pending));
    Bus::assertDispatched(TranscribeMeetingJob::class, fn (TranscribeMeetingJob $job) => $job->meeting->is($failed));

    $failed->refresh();
    expect($failed->status)->toBe('pending')
        ->and($failed->processing_started_at)->toBeNull()
        ->and($failed->processing_completed_at)->toBeNull()
        ->and($failed->error_message)->toBeNull()
        ->and($failed->technical_error)->toBeNull();
});

it('does not queue a meeting with an existing queued transcription job', function () {
    Bus::fake();

    $meeting = Meeting::query()->create([
        'client_id' => Client::factory()->create()->id,
        'title' => 'Already queued meeting',
        'video_path' => 'meetings/already-queued/video.mp4',
        'status' => 'failed',
    ]);

    DB::table('jobs')->insert([
        'queue' => 'default',
        'payload' => json_encode([
            'displayName' => TranscribeMeetingJob::class,
            'data' => [
                'commandName' => TranscribeMeetingJob::class,
                'command' => 'O:29:"App\\Jobs\\TranscribeMeetingJob":1:{s:7:"meeting";O:45:"Illuminate\\Contracts\\Database\\ModelIdentifier":1:{s:2:"id";i:'.$meeting->id.';}',
            ],
        ]),
        'attempts' => 0,
        'available_at' => now()->timestamp,
        'created_at' => now()->timestamp,
    ]);

    $this->artisan('app:process-meetings')
        ->expectsOutput("Skipped meeting {$meeting->id}: transcription job is already queued or running")
        ->assertSuccessful();

    expect($meeting->fresh()->status)->toBe('failed');
});

it('supports dry runs without dispatching or changing meetings', function () {
    Bus::fake();

    $meeting = Meeting::query()->create([
        'client_id' => Client::factory()->create()->id,
        'title' => 'Dry run meeting',
        'video_path' => 'meetings/dry-run/video.mp4',
        'status' => 'failed',
        'error_message' => 'Original error',
    ]);

    $this->artisan('app:process-meetings --dry-run')
        ->expectsOutput("Would queue meeting {$meeting->id}: {$meeting->title}")
        ->assertSuccessful();

    Bus::assertNothingDispatched();
    expect($meeting->fresh()->status)->toBe('failed')
        ->and($meeting->fresh()->error_message)->toBe('Original error');
});

it('makes transcription jobs unique per meeting', function () {
    $job = new TranscribeMeetingJob(Meeting::factory()->create());

    expect($job)->toBeInstanceOf(ShouldBeUnique::class)
        ->and($job->uniqueId())->toBe((string) $job->meeting->id)
        ->and($job->timeout)->toBe(10800)
        ->and($job->failOnTimeout)->toBeTrue()
        ->and(isset($job->uniqueFor))->toBeFalse();
});
