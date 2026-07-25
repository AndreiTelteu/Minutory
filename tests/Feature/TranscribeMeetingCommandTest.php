<?php

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Bus\UniqueLock;
use Illuminate\Contracts\Cache\Repository as Cache;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Bus;
use Illuminate\Support\Facades\DB;

it('dispatches transcription work through the queue', function () {
    expect(new TranscribeMeetingJob(Meeting::factory()->make()))->toBeInstanceOf(ShouldQueue::class);
});

it('queues a meeting for retranscription with the selected driver', function () {
    Bus::fake();

    $meeting = Meeting::query()->create([
        'client_id' => Client::factory()->create()->id,
        'title' => 'Retranscribe me',
        'video_path' => 'meetings/retranscribe/video.mp4',
        'status' => 'completed',
        'processing_started_at' => now()->subMinute(),
        'processing_completed_at' => now(),
        'error_message' => 'old error',
        'technical_error' => 'old technical error',
    ]);

    $this->artisan("meeting:transcribe {$meeting->id} whisper")
        ->expectsOutput("Queued meeting {$meeting->id} for retranscription with whisper.")
        ->assertSuccessful();

    Bus::assertDispatched(
        TranscribeMeetingJob::class,
        fn (TranscribeMeetingJob $job) => $job->meeting->is($meeting) && $job->driver === 'whisper'
    );

    expect($meeting->fresh()->status)->toBe('pending')
        ->and($meeting->fresh()->processing_started_at)->toBeNull()
        ->and($meeting->fresh()->processing_completed_at)->toBeNull()
        ->and($meeting->fresh()->error_message)->toBeNull()
        ->and($meeting->fresh()->technical_error)->toBeNull();
});

it('rejects unsupported transcription drivers', function () {
    Bus::fake();
    $meeting = Meeting::factory()->create();

    $this->artisan("meeting:transcribe {$meeting->id} invalid")
        ->expectsOutput("Unsupported driver 'invalid'. Choose parakeet, whisper, or qwen.")
        ->assertFailed();

    Bus::assertNothingDispatched();
});

it('fails when the meeting does not exist', function () {
    Bus::fake();

    $this->artisan('meeting:transcribe 999999 parakeet')
        ->expectsOutput('Meeting 999999 not found.')
        ->assertFailed();

    Bus::assertNothingDispatched();
});

it('does not reset or dispatch a meeting with an active transcription job', function () {
    Bus::fake();
    $meeting = Meeting::factory()->create(['status' => 'processing']);

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
        'reserved_at' => now()->timestamp,
        'available_at' => now()->timestamp,
        'created_at' => now()->timestamp,
    ]);

    $this->artisan("meeting:transcribe {$meeting->id} qwen")
        ->expectsOutput("Meeting {$meeting->id} already has a transcription job queued or running.")
        ->assertFailed();

    Bus::assertNothingDispatched();
    expect($meeting->fresh()->status)->toBe('processing');
});

it('clears a stale unique lock and dispatches the retranscription job', function () {
    Bus::fake();
    $meeting = Meeting::factory()->create(['status' => 'completed']);
    $staleJob = new TranscribeMeetingJob($meeting, 'parakeet');
    $uniqueLock = new UniqueLock(app(Cache::class));

    expect($uniqueLock->acquire($staleJob))->toBeTrue();

    $this->artisan("meeting:transcribe {$meeting->id} whisper")
        ->expectsOutput("Queued meeting {$meeting->id} for retranscription with whisper.")
        ->assertSuccessful();

    Bus::assertDispatched(
        TranscribeMeetingJob::class,
        fn (TranscribeMeetingJob $job) => $job->meeting->is($meeting) && $job->driver === 'whisper'
    );
});
