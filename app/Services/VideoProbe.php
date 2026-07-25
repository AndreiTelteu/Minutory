<?php

namespace App\Services;

use App\Exceptions\WorkerApiException;
use Symfony\Component\Process\Exception\ProcessTimedOutException;
use Symfony\Component\Process\Process;

class VideoProbe
{
    public function validate(string $path): void
    {
        $process = new Process([
            (string) config('services.worker.artifacts.video.ffprobe_path', 'ffprobe'),
            '-v',
            'error',
            '-select_streams',
            'v:0',
            '-show_entries',
            'stream=codec_type',
            '-of',
            'json',
            $path,
        ]);
        $process->setTimeout((float) config('services.worker.artifacts.video.ffprobe_timeout', 15));

        try {
            $process->run();
        } catch (ProcessTimedOutException) {
            throw new WorkerApiException(
                'invalid_video',
                'The uploaded video could not be read within the configured probe timeout.',
                422,
            );
        } catch (\Throwable) {
            throw new WorkerApiException(
                'invalid_video',
                'The uploaded video could not be inspected.',
                422,
            );
        }

        if (! $process->isSuccessful()) {
            throw new WorkerApiException(
                'invalid_video',
                'The uploaded file is not a readable video.',
                422,
            );
        }

        try {
            $output = json_decode($process->getOutput(), true, 16, JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            throw new WorkerApiException(
                'invalid_video',
                'The uploaded video probe returned an invalid result.',
                422,
            );
        }

        if (! is_array($output)
            || ! isset($output['streams'])
            || ! is_array($output['streams'])
            || ! collect($output['streams'])->contains(
                fn (mixed $stream): bool => is_array($stream) && ($stream['codec_type'] ?? null) === 'video'
            )) {
            throw new WorkerApiException(
                'invalid_video',
                'The uploaded file does not contain a video stream.',
                422,
            );
        }
    }
}
