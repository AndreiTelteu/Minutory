<?php

namespace App\Console\Commands;

use App\Jobs\TranscribeMeetingJob;
use App\Models\Meeting;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;

class ProcessMeetings extends Command
{
    /**
     * @var string
     */
    protected $signature = 'app:process-meetings {--dry-run : Show meetings that would be queued without dispatching jobs}';

    /**
     * @var string
     */
    protected $description = 'Queue pending and failed meetings that do not already have an active transcription job';

    public function handle(): int
    {
        $meetings = Meeting::query()
            ->whereIn('status', ['pending', 'failed'])
            ->orderBy('id')
            ->get();

        if ($meetings->isEmpty()) {
            $this->info('No pending or failed meetings found.');

            return self::SUCCESS;
        }

        $queued = 0;

        foreach ($meetings as $meeting) {
            if ($this->hasActiveTranscriptionJob($meeting)) {
                $this->line("Skipped meeting {$meeting->id}: transcription job is already queued or running");

                continue;
            }

            if ($this->option('dry-run')) {
                $this->line("Would queue meeting {$meeting->id}: {$meeting->title}");

                continue;
            }

            $meeting->update([
                'status' => 'pending',
                'processing_started_at' => null,
                'processing_completed_at' => null,
                'error_message' => null,
                'technical_error' => null,
            ]);

            // TranscribeMeetingJob is unique per meeting, so Laravel only puts a
            // job on the queue when this meeting has no active or pending job.
            TranscribeMeetingJob::dispatch($meeting);

            $queued++;
            $this->line("Queued meeting {$meeting->id}: {$meeting->title}");
        }

        $this->info("Processed {$meetings->count()} meeting(s); queued {$queued} transcription job(s).");

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
