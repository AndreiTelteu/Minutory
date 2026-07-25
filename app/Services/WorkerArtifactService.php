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
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

class WorkerArtifactService
{
    public function __construct(
        private readonly TranscriptImporter $transcriptImporter,
        private readonly Dispatcher $dispatcher,
    ) {}

    /**
     * @return array{state: string, sha256: string, bytes: int}
     */
    public function storeVideo(Meeting $meeting, UploadedFile $upload, bool $replace): array
    {
        $this->ingestionFor($meeting);

        $extension = config('services.worker.artifacts.video.extensions.'.$upload->getMimeType());
        if (! is_string($extension)) {
            throw new WorkerApiException('validation_failed', 'The video type is not supported.', 422);
        }

        $target = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR."video.{$extension}";
        $staged = $this->stageUpload($meeting, $upload, 'video');
        $hash = hash_file('sha256', $staged);
        $bytes = File::size($staged);

        $result = $this->storeBinaryArtifact(
            $meeting,
            'video',
            $staged,
            $target,
            $hash,
            $bytes,
            $replace,
            function (WorkerIngestion $ingestion) use ($meeting, $target): void {
                $oldVideoPath = $meeting->video_path;
                $relativePath = $this->relativePublicPath($target);

                $meeting->update(['video_path' => $relativePath]);

                if ($oldVideoPath !== null && $oldVideoPath !== $relativePath) {
                    Storage::disk('public')->delete($oldVideoPath);
                }
            },
        );

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
        } catch (Throwable $exception) {
            File::delete($staged);
            throw $exception;
        }

        return $this->storeBinaryArtifact(
            $meeting,
            'audio',
            $staged,
            $target,
            hash_file('sha256', $staged),
            File::size($staged),
            $replace,
        );
    }

    /**
     * @return array{state: string, sha256: string, bytes: int, segments: int}
     */
    public function storeTranscript(Meeting $meeting, UploadedFile $upload, bool $replace): array
    {
        $ingestion = $this->ingestionFor($meeting);
        $target = $this->artifactDirectory($meeting).DIRECTORY_SEPARATOR.'transcript.json';
        $staged = $this->stageUpload($meeting, $upload, 'transcript');
        $hash = hash_file('sha256', $staged);
        $bytes = File::size($staged);

        if ($ingestion->transcript_sha256 === $hash && File::exists($target)) {
            File::delete($staged);

            return [
                'state' => 'already_uploaded',
                'sha256' => $hash,
                'bytes' => $bytes,
                'segments' => $meeting->transcriptions()->count(),
            ];
        }

        if ($ingestion->transcript_sha256 !== null
            && $ingestion->transcript_sha256 !== $hash
            && ! $replace) {
            File::delete($staged);
            throw new WorkerApiException(
                'artifact_hash_conflict',
                'A different transcript artifact is already stored. Set replace=true to replace it.',
                409,
            );
        }

        try {
            $segments = $this->transcriptImporter->replace(
                $meeting,
                $staged,
                $target,
                function () use ($meeting, $hash, $bytes): void {
                    WorkerIngestion::query()
                        ->where('meeting_id', $meeting->id)
                        ->update([
                            'transcript_sha256' => $hash,
                            'transcript_bytes' => $bytes,
                            'transcript_uploaded_at' => now(),
                            'updated_at' => now(),
                        ]);

                    $meeting->update([
                        'status' => 'completed',
                        'processing_completed_at' => now(),
                        'error_message' => null,
                        'technical_error' => null,
                    ]);
                },
            );
        } catch (WorkerApiException $exception) {
            throw $exception;
        } catch (InvalidTranscriptException $exception) {
            File::delete($staged);
            throw new WorkerApiException(
                'invalid_transcript',
                $exception->getMessage(),
                422,
            );
        }

        return [
            'state' => 'uploaded',
            'sha256' => $hash,
            'bytes' => $bytes,
            'segments' => $segments,
        ];
    }

    /**
     * @param  null|callable(WorkerIngestion): void  $afterStore
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
        ?callable $afterStore = null,
    ): array {
        $ingestion = $this->ingestionFor($meeting);
        $hashField = "{$artifact}_sha256";
        $bytesField = "{$artifact}_bytes";
        $uploadedAtField = "{$artifact}_uploaded_at";

        if ($ingestion->{$hashField} === $hash && File::exists($target)) {
            File::delete($staged);

            return ['state' => 'already_uploaded', 'sha256' => $hash, 'bytes' => $bytes];
        }

        if ($ingestion->{$hashField} !== null && $ingestion->{$hashField} !== $hash && ! $replace) {
            File::delete($staged);
            throw new WorkerApiException(
                'artifact_hash_conflict',
                "A different {$artifact} artifact is already stored. Set replace=true to replace it.",
                409,
            );
        }

        $backup = null;
        $replaced = false;

        try {
            DB::transaction(function () use (

                $ingestion,
                $hashField,
                $bytesField,
                $uploadedAtField,
                $hash,
                $bytes,
                $staged,
                $target,
                $afterStore,
                &$backup,
                &$replaced,
            ): void {
                if (File::exists($target)) {
                    $backup = $target.'.backup.'.bin2hex(random_bytes(8));
                    if (! rename($target, $backup)) {
                        throw new RuntimeException('Unable to prepare the existing artifact for replacement.');
                    }
                }

                if (! rename($staged, $target)) {
                    if ($backup !== null) {
                        rename($backup, $target);
                    }

                    throw new RuntimeException('Unable to store the artifact.');
                }
                $replaced = true;

                $ingestion->update([
                    $hashField => $hash,
                    $bytesField => $bytes,
                    $uploadedAtField => now(),
                ]);

                $afterStore?->__invoke($ingestion);
            });
        } catch (Throwable $exception) {
            if ($replaced && File::exists($target)) {
                File::delete($target);
            }
            if ($backup !== null && File::exists($backup)) {
                rename($backup, $target);
            }

            throw $exception;
        } finally {
            if ($backup !== null && File::exists($backup)) {
                File::delete($backup);
            }
            if (File::exists($staged)) {
                File::delete($staged);
            }
        }

        return ['state' => 'uploaded', 'sha256' => $hash, 'bytes' => $bytes];
    }

    private function stageUpload(Meeting $meeting, UploadedFile $upload, string $artifact): string
    {
        $maximumBytes = (int) config("services.worker.artifacts.{$artifact}.max_bytes");
        $bytes = $upload->getSize();
        if (! is_int($bytes) || $bytes > $maximumBytes) {
            throw new WorkerApiException('validation_failed', 'The uploaded artifact exceeds the configured limit.', 422);
        }

        $directory = $this->artifactDirectory($meeting);
        File::ensureDirectoryExists($directory);
        $staged = $directory.DIRECTORY_SEPARATOR.'.'.$artifact.'.'.bin2hex(random_bytes(12)).'.tmp';

        $source = fopen($upload->getRealPath(), 'rb');
        $destination = fopen($staged, 'xb');
        if ($source === false || $destination === false) {
            is_resource($source) && fclose($source);
            is_resource($destination) && fclose($destination);
            File::delete($staged);
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
            $ingestion = WorkerIngestion::query()
                ->where('meeting_id', $meeting->id)
                ->lockForUpdate()
                ->firstOrFail();

            if (! $ingestion->start_transcript_server
                || $ingestion->server_transcription_dispatched_at !== null) {
                return;
            }

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
        $handle = fopen($path, 'rb');
        if ($handle === false || fread($handle, 4) !== 'RIFF') {
            is_resource($handle) && fclose($handle);
            throw new WorkerApiException('invalid_audio', 'Audio must be a RIFF WAV file.', 422);
        }

        fseek($handle, 8);
        if (fread($handle, 4) !== 'WAVE') {
            fclose($handle);
            throw new WorkerApiException('invalid_audio', 'Audio must be a RIFF WAV file.', 422);
        }

        $format = null;
        while (! feof($handle)) {
            $chunkId = fread($handle, 4);
            $sizeBytes = fread($handle, 4);
            if (strlen($chunkId) !== 4 || strlen($sizeBytes) !== 4) {
                break;
            }

            $chunkSize = unpack('V', $sizeBytes)[1];
            if ($chunkId === 'fmt ') {
                $data = fread($handle, min($chunkSize, 40));
                if (strlen($data) >= 16) {
                    $format = unpack('vaudio_format/vchannels/Vsample_rate/Vbyte_rate/vblock_align/vbits', substr($data, 0, 16));
                }
                break;
            }

            fseek($handle, $chunkSize + ($chunkSize % 2), SEEK_CUR);
        }
        fclose($handle);

        if ($format === null
            || $format['audio_format'] !== 1
            || $format['channels'] !== 1
            || $format['sample_rate'] !== 16_000
            || $format['bits'] !== 16) {
            throw new WorkerApiException(
                'invalid_audio',
                'Audio must be mono 16 kHz 16-bit PCM WAV.',
                422,
            );
        }
    }
}
