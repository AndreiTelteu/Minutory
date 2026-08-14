<?php

namespace App\Services;

use App\Exceptions\InvalidTranscriptException;
use App\Exceptions\WorkerApiException;
use App\Jobs\TranscribeMeetingJob;
use App\Models\Meeting;
use App\Models\WorkerIngestion;
use Illuminate\Contracts\Bus\Dispatcher;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

class WorkerArtifactService
{
    public function __construct(
        private readonly TranscriptImporter $transcriptImporter,
        private readonly SpeakerTurnsImporter $speakerTurnsImporter,
        private readonly SpeakerAssignmentService $speakerAssignment,
        private readonly Dispatcher $dispatcher,
        private readonly AtomicFilesystem $filesystem,
        private readonly VideoProbe $videoProbe,
        private readonly WorkerQueueGuard $queueGuard,
    ) {}

    /**
     * @return array{state: string, sha256: string, bytes: int}
     */
    public function storeVideo(Meeting $meeting, UploadedFile $upload, bool $replace): array
    {
        $ingestion = $this->ingestionFor($meeting);
        if ($ingestion->start_transcript_server) {
            $this->queueGuard->ensureTransactionalDatabaseQueue();
        }

        $extension = strtolower($upload->getClientOriginalExtension());
        if (! in_array($extension, array_values(config('services.worker.artifacts.video.extensions', [])), true)) {
            throw new WorkerApiException('validation_failed', 'The video type is not supported.', 422);
        }

        $target = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR."video.{$extension}";
        $staged = $this->stageUpload($meeting, $upload, 'video');

        try {
            $this->videoProbe->validate($staged);

            $result = $this->storeBinaryArtifact(
                $meeting,
                'video',
                $staged,
                $target,
                hash_file('sha256', $staged),
                File::size($staged),
                $replace,
            );
        } finally {
            $this->filesystem->delete($staged);
        }

        $this->dispatchServerTranscriptionIfNeeded($meeting);

        return $result;
    }

    /**
     * @return array{state: string, sha256: string, bytes: int}
     */
    public function storeAudio(Meeting $meeting, UploadedFile $upload, bool $replace): array
    {
        $this->ingestionFor($meeting);

        $target = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR.'audio.wav';
        $staged = $this->stageUpload($meeting, $upload, 'audio');

        try {
            $this->validateWaveFile($staged);

            return $this->storeBinaryArtifact(
                $meeting,
                'audio',
                $staged,
                $target,
                hash_file('sha256', $staged),
                File::size($staged),
                $replace,
            );
        } finally {
            $this->filesystem->delete($staged);
        }
    }

    /**
     * @return array{state: string, sha256: string, bytes: int, segments: int}
     */
    public function storeTranscript(Meeting $meeting, UploadedFile $upload, bool $replace): array
    {
        $this->ingestionFor($meeting);
        $target = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR.'transcript.json';
        $staged = $this->stageUpload($meeting, $upload, 'transcript');
        $hash = hash_file('sha256', $staged);
        $bytes = File::size($staged);
        $replacement = null;

        try {
            try {
                $segments = $this->transcriptImporter->validateFile($staged);
            } catch (InvalidTranscriptException $exception) {
                throw new WorkerApiException(
                    'invalid_transcript',
                    $exception->getMessage(),
                    422,
                );
            }

            $result = DB::transaction(function () use (
                $meeting,
                $target,
                $staged,
                $hash,
                $bytes,
                $replace,
                $segments,
                &$replacement,
            ): array {
                $ingestion = $this->lockedIngestion($meeting);

                if ($ingestion->transcript_sha256 === $hash && $this->filesystem->exists($target)) {
                    return [
                        'state' => 'already_uploaded',
                        'sha256' => $hash,
                        'bytes' => $bytes,
                        'segments' => $meeting->transcriptions()->count(),
                    ];
                }

                $this->ensureReplacementAllowed($ingestion, 'transcript', $hash, $replace);

                $replacement = $this->filesystem->beginReplacement($staged, $target);
                $count = $this->transcriptImporter->replaceRowsWithinTransaction($meeting, $segments);
                $this->applySpeakersIfAvailable($meeting, $ingestion);

                $ingestion->update([
                    'transcript_sha256' => $hash,
                    'transcript_bytes' => $bytes,
                    'transcript_uploaded_at' => now(),
                ]);

                Meeting::query()
                    ->whereKey($meeting->id)
                    ->lockForUpdate()
                    ->firstOrFail()
                    ->update([
                        'status' => 'completed',
                        'processing_completed_at' => now(),
                        'error_message' => null,
                        'technical_error' => null,
                    ]);

                return [
                    'state' => 'uploaded',
                    'sha256' => $hash,
                    'bytes' => $bytes,
                    'segments' => $count,
                ];
            });

        } catch (Throwable $exception) {
            $replacement?->rollback();

            throw $exception;
        } finally {
            $this->filesystem->delete($staged);
        }

        $replacement?->commit();

        return $result;
    }

    /**
     * @return array{state: string, sha256: string, bytes: int, turns: int}
     */
    public function storeSpeakers(Meeting $meeting, UploadedFile $upload, bool $replace): array
    {
        $this->ingestionFor($meeting);
        $target = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR.'speakers.json';
        $staged = $this->stageUpload($meeting, $upload, 'speakers');
        $hash = hash_file('sha256', $staged);
        $bytes = File::size($staged);
        $replacement = null;

        try {
            try {
                $turns = $this->speakerTurnsImporter->validateFile($staged);
            } catch (InvalidTranscriptException $exception) {
                throw new WorkerApiException('invalid_speakers', $exception->getMessage(), 422);
            }

            $result = DB::transaction(function () use ($meeting, $target, $staged, $hash, $bytes, $replace, $turns, &$replacement): array {
                $ingestion = $this->lockedIngestion($meeting);
                if ($ingestion->speakers_sha256 === $hash && $this->filesystem->exists($target)) {
                    return [
                        'state' => 'already_uploaded',
                        'sha256' => $hash,
                        'bytes' => $bytes,
                        'turns' => count($turns),
                    ];
                }
                $this->ensureReplacementAllowed($ingestion, 'speakers', $hash, $replace);
                $replacement = $this->filesystem->beginReplacement($staged, $target);
                $ingestion->update([
                    'speakers_sha256' => $hash,
                    'speakers_bytes' => $bytes,
                    'speakers_uploaded_at' => now(),
                ]);
                $this->speakerAssignment->apply($meeting, $turns);

                return ['state' => 'uploaded', 'sha256' => $hash, 'bytes' => $bytes, 'turns' => count($turns)];
            });
        } catch (Throwable $exception) {
            $replacement?->rollback();
            throw $exception;
        } finally {
            $this->filesystem->delete($staged);
        }

        $replacement?->commit();

        return $result;
    }

    /**
     * @return array{state: string, sha256: string, bytes: int}
     */
    private function storeBinaryArtifact(
        Meeting $meeting,
        string $artifact,
        string $staged,
        string $target,
        string $hash,
        int $bytes,
        bool $replace,
    ): array {
        $replacement = null;
        $oldVideoPath = null;

        try {
            $result = DB::transaction(function () use (
                $meeting,
                $artifact,
                $staged,
                $target,
                $hash,
                $bytes,
                $replace,
                &$replacement,
                &$oldVideoPath,
            ): array {
                $ingestion = $this->lockedIngestion($meeting);
                $lockedMeeting = $artifact === 'video'
                    ? Meeting::query()->whereKey($meeting->id)->lockForUpdate()->firstOrFail()
                    : null;

                $existingPath = $artifact === 'video' && $lockedMeeting?->video_path !== null
                    ? Storage::disk('public')->path($lockedMeeting->video_path)
                    : $target;

                $hashField = "{$artifact}_sha256";
                if ($ingestion->{$hashField} === $hash && $this->filesystem->exists($existingPath)) {
                    return ['state' => 'already_uploaded', 'sha256' => $hash, 'bytes' => $bytes];
                }

                $this->ensureReplacementAllowed($ingestion, $artifact, $hash, $replace);

                $replacement = $this->filesystem->beginReplacement($staged, $target);
                $ingestion->update([
                    $hashField => $hash,
                    "{$artifact}_bytes" => $bytes,
                    "{$artifact}_uploaded_at" => now(),
                ]);

                if ($lockedMeeting !== null) {
                    $oldVideoPath = $lockedMeeting->video_path;
                    $lockedMeeting->update([
                        'video_path' => $this->relativePublicPath($target),
                    ]);
                }

                return ['state' => 'uploaded', 'sha256' => $hash, 'bytes' => $bytes];
            });

        } catch (Throwable $exception) {
            $replacement?->rollback();

            throw $exception;
        }

        $replacement?->commit();

        if ($replacement !== null && $oldVideoPath !== null) {
            $newVideoPath = $this->relativePublicPath($target);
            if ($oldVideoPath !== $newVideoPath) {
                $oldAbsolutePath = Storage::disk('public')->path($oldVideoPath);

                try {
                    $deleted = $this->filesystem->delete($oldAbsolutePath);
                } catch (Throwable $exception) {
                    $deleted = false;
                    Log::warning('Obsolete video artifact cleanup raised an exception.', [
                        'path' => $oldAbsolutePath,
                        'meeting_id' => $meeting->id,
                        'error' => $exception->getMessage(),
                    ]);
                }

                if (! $deleted) {
                    Log::warning('Obsolete video artifact could not be removed after commit.', [
                        'path' => $oldAbsolutePath,
                        'meeting_id' => $meeting->id,
                    ]);
                }
            }
        }

        return $result;
    }

    private function applySpeakersIfAvailable(Meeting $meeting, WorkerIngestion $ingestion): void
    {
        if ($ingestion->speakers_sha256 === null) {
            return;
        }

        $path = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR.'speakers.json';
        if (! $this->filesystem->exists($path)) {
            return;
        }

        $this->speakerAssignment->apply($meeting, $this->speakerTurnsImporter->validateFile($path));
    }

    private function ensureReplacementAllowed(
        WorkerIngestion $ingestion,
        string $artifact,
        string $hash,
        bool $replace,
    ): void {
        $existingHash = $ingestion->getAttribute("{$artifact}_sha256");

        if ($existingHash !== null && $existingHash !== $hash && ! $replace) {
            throw new WorkerApiException(
                'artifact_hash_conflict',
                "A different {$artifact} artifact is already stored. Set replace=true to replace it.",
                409,
            );
        }
    }

    private function stageUpload(Meeting $meeting, UploadedFile $upload, string $artifact): string
    {
        if (! $upload->isValid()) {
            throw new WorkerApiException(
                'upload_failed',
                'PHP could not accept the uploaded artifact.',
                422,
            );
        }

        $maximumBytes = (int) config("services.worker.artifacts.{$artifact}.max_bytes");
        $bytes = $upload->getSize();
        if (! is_int($bytes) || $bytes > $maximumBytes) {
            throw new WorkerApiException('validation_failed', 'The uploaded artifact exceeds the configured limit.', 422);
        }

        $directory = $this->artifactDirectory($meeting);
        $this->filesystem->ensureDirectory($directory);
        $staged = $directory.DIRECTORY_SEPARATOR.'.'.$artifact.'.'.bin2hex(random_bytes(12)).'.tmp';

        $source = fopen($upload->getRealPath(), 'rb');
        $destination = fopen($staged, 'xb');
        if ($source === false || $destination === false) {
            is_resource($source) && fclose($source);
            is_resource($destination) && fclose($destination);
            $this->filesystem->delete($staged);
            throw new RuntimeException('Unable to stage the uploaded artifact.');
        }

        try {
            if (stream_copy_to_stream($source, $destination) === false) {
                throw new RuntimeException('Unable to stage the uploaded artifact.');
            }
            fflush($destination);
        } finally {
            fclose($source);
            fclose($destination);
        }

        return $staged;
    }

    private function dispatchServerTranscriptionIfNeeded(Meeting $meeting): void
    {
        DB::transaction(function () use ($meeting): void {
            $ingestion = $this->lockedIngestion($meeting);

            if (! $ingestion->start_transcript_server
                || $ingestion->server_transcription_dispatched_at !== null) {
                return;
            }

            $this->queueGuard->ensureTransactionalDatabaseQueue();

            // This deliberately bypasses ShouldBeUnique's PendingDispatch lock.
            // The worker API's locked ingestion row and durable marker are the
            // uniqueness mechanism, and the guard ensures the queue insert and
            // marker use this same database transaction.
            $this->dispatcher->dispatch(new TranscribeMeetingJob($meeting->fresh()));

            $ingestion->update([
                'server_transcription_dispatched_at' => now(),
            ]);
        });
    }

    private function ingestionFor(Meeting $meeting): WorkerIngestion
    {
        $ingestion = $meeting->workerIngestion()->first();
        if ($ingestion === null) {
            throw new WorkerApiException(
                'worker_meeting_not_found',
                'The meeting is not managed by the worker API.',
                404,
            );
        }

        return $ingestion;
    }

    private function lockedIngestion(Meeting $meeting): WorkerIngestion
    {
        $ingestion = WorkerIngestion::query()
            ->where('meeting_id', $meeting->id)
            ->lockForUpdate()
            ->first();

        if ($ingestion === null) {
            throw new WorkerApiException(
                'worker_meeting_not_found',
                'The meeting is not managed by the worker API.',
                404,
            );
        }

        return $ingestion;
    }

    private function artifactDirectory(Meeting $meeting): string
    {
        return Storage::disk('public')->path("meetings/{$meeting->client_id}/{$meeting->id}");
    }

    private function relativePublicPath(string $absolutePath): string
    {
        $root = rtrim(Storage::disk('public')->path(''), DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR;

        return str_replace(DIRECTORY_SEPARATOR, '/', substr($absolutePath, strlen($root)));
    }

    private function validateWaveFile(string $path): void
    {
        $fileSize = File::size($path);
        $handle = fopen($path, 'rb');
        if ($handle === false) {
            throw $this->invalidAudio();
        }

        try {
            $header = fread($handle, 12);
            if (strlen($header) !== 12
                || substr($header, 0, 4) !== 'RIFF'
                || substr($header, 8, 4) !== 'WAVE') {
                throw $this->invalidAudio();
            }

            $riffSize = unpack('V', substr($header, 4, 4))[1];
            if ($riffSize + 8 !== $fileSize) {
                throw $this->invalidAudio();
            }

            $format = null;
            $dataSize = null;
            $offset = 12;

            while ($offset + 8 <= $fileSize) {
                fseek($handle, $offset);
                $chunkHeader = fread($handle, 8);
                if (strlen($chunkHeader) !== 8) {
                    throw $this->invalidAudio();
                }

                $chunkId = substr($chunkHeader, 0, 4);
                $chunkSize = unpack('V', substr($chunkHeader, 4, 4))[1];
                $chunkDataStart = $offset + 8;
                $chunkDataEnd = $chunkDataStart + $chunkSize;
                $paddedEnd = $chunkDataEnd + ($chunkSize % 2);

                if ($chunkDataEnd > $fileSize || $paddedEnd > $fileSize) {
                    throw $this->invalidAudio();
                }

                if ($chunkId === 'fmt ') {
                    if ($chunkSize < 16) {
                        throw $this->invalidAudio();
                    }

                    fseek($handle, $chunkDataStart);
                    $data = fread($handle, 16);
                    if (strlen($data) !== 16) {
                        throw $this->invalidAudio();
                    }

                    $format = unpack(
                        'vaudio_format/vchannels/Vsample_rate/Vbyte_rate/vblock_align/vbits',
                        $data,
                    );
                } elseif ($chunkId === 'data') {
                    $dataSize = $chunkSize;
                }

                $offset = $paddedEnd;
            }

            $expectedBlockAlign = 2;
            $expectedByteRate = 16_000 * $expectedBlockAlign;

            if ($offset !== $fileSize
                || $format === null
                || $dataSize === null
                || $dataSize <= 0
                || $format['audio_format'] !== 1
                || $format['channels'] !== 1
                || $format['sample_rate'] !== 16_000
                || $format['bits'] !== 16
                || $format['block_align'] !== $expectedBlockAlign
                || $format['byte_rate'] !== $expectedByteRate
                || $dataSize % $format['block_align'] !== 0) {
                throw $this->invalidAudio();
            }
        } finally {
            fclose($handle);
        }
    }

    private function invalidAudio(): WorkerApiException
    {
        return new WorkerApiException(
            'invalid_audio',
            'Audio must be a complete mono 16 kHz 16-bit PCM WAV file.',
            422,
        );
    }
}
