<?php

namespace App\Services;

use App\Exceptions\WorkerApiException;
use App\Models\Meeting;
use App\Models\WorkerIngestion;
use Carbon\CarbonImmutable;
use Illuminate\Database\QueryException;
use Illuminate\Support\Facades\DB;

class WorkerMeetingService
{
    /**
     * @return array{meeting: Meeting, created: bool}
     */
    public function createOrReplay(array $metadata): array
    {
        $canonical = [
            'client_id' => (int) $metadata['client_id'],
            'title' => trim($metadata['title']),
            'meeting_at' => isset($metadata['meeting_at'])
                ? CarbonImmutable::parse($metadata['meeting_at'])->utc()
                : null,
            'duration' => isset($metadata['duration_seconds'])
                ? (int) $metadata['duration_seconds']
                : null,
            'start_transcript_server' => (bool) $metadata['start_transcript_server'],
        ];

        try {
            return DB::transaction(function () use ($metadata, $canonical): array {
                $ingestion = WorkerIngestion::query()
                    ->where('worker_item_id', $metadata['worker_item_id'])
                    ->lockForUpdate()
                    ->first();

                if ($ingestion !== null) {
                    return $this->replay($ingestion, $canonical);
                }

                $meeting = Meeting::query()->create([
                    'client_id' => $canonical['client_id'],
                    'title' => $canonical['title'],
                    'meeting_at' => $canonical['meeting_at'],
                    'duration' => $canonical['duration'],
                    'video_path' => null,
                    'status' => 'pending',
                    'uploaded_at' => now(),
                ]);

                $meeting->workerIngestion()->create([
                    'worker_item_id' => $metadata['worker_item_id'],
                    'start_transcript_server' => $canonical['start_transcript_server'],
                ]);

                return ['meeting' => $meeting->load('workerIngestion'), 'created' => true];
            });
        } catch (QueryException $exception) {
            if (! $this->isUniqueViolation($exception)) {
                throw $exception;
            }

            $ingestion = WorkerIngestion::query()
                ->where('worker_item_id', $metadata['worker_item_id'])
                ->firstOrFail();

            return $this->replay($ingestion, $canonical);
        }
    }

    /**
     * @return array{meeting: Meeting, created: false}
     */
    private function replay(WorkerIngestion $ingestion, array $canonical): array
    {
        $meeting = $ingestion->meeting;

        $storedMeetingAt = $meeting->meeting_at?->utc()->format('Y-m-d H:i:s');
        $requestedMeetingAt = $canonical['meeting_at']?->format('Y-m-d H:i:s');

        $matches = (int) $meeting->client_id === $canonical['client_id']
            && $meeting->title === $canonical['title']
            && $storedMeetingAt === $requestedMeetingAt
            && $meeting->duration === $canonical['duration']
            && $ingestion->start_transcript_server === $canonical['start_transcript_server'];

        if (! $matches) {
            throw new WorkerApiException(
                'meeting_metadata_conflict',
                'The worker item ID is already associated with different canonical metadata.',
                409,
            );
        }

        return ['meeting' => $meeting->setRelation('workerIngestion', $ingestion), 'created' => false];
    }

    private function isUniqueViolation(QueryException $exception): bool
    {
        return in_array((string) ($exception->errorInfo[0] ?? ''), ['23000', '23505'], true);
    }
}
