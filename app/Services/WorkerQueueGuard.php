<?php

namespace App\Services;

use App\Exceptions\WorkerApiException;

class WorkerQueueGuard
{
    public function ensureTransactionalDatabaseQueue(): void
    {
        $queueConnection = (string) config('queue.default');
        $queueConfig = config("queue.connections.{$queueConnection}");
        $databaseConnection = (string) config('database.default');

        $supported = is_array($queueConfig)
            && ($queueConfig['driver'] ?? null) === 'database'
            && ($queueConfig['after_commit'] ?? false) === false
            && (($queueConfig['connection'] ?? null) === null
                || (string) $queueConfig['connection'] === $databaseConnection);

        if (! $supported) {
            throw new WorkerApiException(
                'unsupported_server_transcription_queue',
                'Server transcription requires a database queue on the application database connection.',
                503,
            );
        }
    }
}
