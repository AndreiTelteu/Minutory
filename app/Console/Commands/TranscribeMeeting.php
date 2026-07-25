<?php

namespace App\Console\Commands;

use App\Jobs\TranscribeMeetingJob;
use App\Models\Meeting;
use Illuminate\Bus\UniqueLock;
use Illuminate\Console\Command;
use Illuminate\Contracts\Bus\Dispatcher;
use Illuminate\Contracts\Cache\Repository as Cache;
use Illuminate\Support\Facades\DB;

class TranscribeMeeting extends Command
{
    protected $signature = 'meeting:transcribe
        {meeting : Meeting ID}
        {driver : Transcription driver (parakeet, whisper, qwen)}';

    protected $description = 'Queue a meeting for retranscription with a selected driver and replace its transcript on success';

    public function handle(): int
    {
        $driver = strtolower((string) $this->argument('driver'));
        if (! in_array($driver, ['parakeet', 'whisper', 'qwen'], true)) {
            $this->error("Unsupported driver '{$driver}'. Choose parakeet, whisper, or qwen.");

            return self::FAILURE;
        }

        $meeting = Meeting::query()->find($this->argument('meeting'));
        if (! $meeting) {
            $this->error("Meeting {$this->argument('meeting')} not found.");

            return self::FAILURE;
        }

        if ($this->hasActiveTranscriptionJob($meeting)) {
            $this->error("Meeting {$meeting->id} already has a transcription job queued or running.");

            return self::FAILURE;
        }

        $job = new TranscribeMeetingJob($meeting, $driver);
        $uniqueLock = new UniqueLock(app(Cache::class));

        // A worker/container killed during processing can leave Laravel's unique
        // lock behind even though the database queue no longer contains the job.
        $uniqueLock->release($job);

        if (! $uniqueLock->acquire($job)) {
            $this->error("Could not acquire the transcription lock for meeting {$meeting->id}.");

            return self::FAILURE;
        }

        $previousState = $meeting->only([
            'status',
            'processing_started_at',
            'processing_completed_at',
            'error_message',
            'technical_error',
        ]);

        $meeting->update([
            'status' => 'pending',
            'processing_started_at' => null,
            'processing_completed_at' => null,
            'error_message' => null,
            'technical_error' => null,
        ]);

        try {
            app(Dispatcher::class)->dispatch($job);
        } catch (\Throwable $exception) {
            $uniqueLock->release($job);
            $meeting->update($previousState);
            $this->error("Could not queue meeting {$meeting->id}: {$exception->getMessage()}");

            return self::FAILURE;
        }

        $this->info("Queued meeting {$meeting->id} for retranscription with {$driver}.");
        $this->line('The existing transcript remains available until the new transcript is generated successfully.');

        return self::SUCCESS;
    }

    private function hasActiveTranscriptionJob(Meeting $meeting): bool
    {
        $needle = '"id";i:'.$meeting->getKey().';';

        return DB::table(config('queue.connections.database.table', 'jobs'))
            ->pluck('payload')
            ->contains(function (string $payload) use ($needle): bool {
                $decoded = json_decode($payload, true);
                $command = $decoded['data']['command'] ?? '';

                return ($decoded['displayName'] ?? null) === TranscribeMeetingJob::class
                    && is_string($command)
                    && str_contains($command, $needle);
            });
    }
}
