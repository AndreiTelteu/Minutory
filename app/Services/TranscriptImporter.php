<?php

namespace App\Services;

use App\Exceptions\InvalidTranscriptException;
use App\Models\Meeting;
use App\Models\Transcription;
use Closure;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use RuntimeException;
use Throwable;

class TranscriptImporter
{
    /**
     * Validate and import a transcript already stored at its durable path.
     */
    public function import(Meeting $meeting, string $path): int
    {
        $segments = $this->validateFile($path);

        return DB::transaction(fn (): int => $this->replaceRows($meeting, $segments));
    }

    /**
     * Validate a staged transcript, then atomically replace its file and rows.
     *
     * The callback participates in the same database transaction as the rows.
     */
    public function replace(
        Meeting $meeting,
        string $stagedPath,
        string $destinationPath,
        ?Closure $afterImport = null,
    ): int {
        $segments = $this->validateFile($stagedPath);
        $backupPath = null;
        $fileReplaced = false;

        try {
            return DB::transaction(function () use (
                $meeting,
                $segments,
                $stagedPath,
                $destinationPath,
                $afterImport,
                &$backupPath,
                &$fileReplaced,
            ): int {
                File::ensureDirectoryExists(dirname($destinationPath));

                if (File::exists($destinationPath)) {
                    $backupPath = $destinationPath.'.backup.'.bin2hex(random_bytes(8));
                    if (! rename($destinationPath, $backupPath)) {
                        throw new RuntimeException('Unable to prepare the existing transcript for replacement.');
                    }
                }

                if (! rename($stagedPath, $destinationPath)) {
                    if ($backupPath !== null) {
                        rename($backupPath, $destinationPath);
                    }

                    throw new RuntimeException('Unable to store the transcript artifact.');
                }

                $fileReplaced = true;
                $count = $this->replaceRows($meeting, $segments);
                $afterImport?->__invoke($count);

                return $count;
            });
        } catch (Throwable $exception) {
            if ($fileReplaced && File::exists($destinationPath)) {
                File::delete($destinationPath);
            }

            if ($backupPath !== null && File::exists($backupPath)) {
                rename($backupPath, $destinationPath);
            }

            throw $exception;
        } finally {
            if ($backupPath !== null && File::exists($backupPath)) {
                File::delete($backupPath);
            }
        }
    }

    /**
     * @return list<array{speaker: ?string, text: string, start: float, end: float, confidence: ?float, has_confidence: bool}>
     */
    public function validateFile(string $path): array
    {
        if (! File::isFile($path)) {
            throw new InvalidTranscriptException("Transcript file not found at: {$path}");
        }

        $size = File::size($path);
        $maximumBytes = (int) config('services.worker.artifacts.transcript.max_bytes', 52_428_800);

        if ($size > $maximumBytes) {
            throw new InvalidTranscriptException('Transcript exceeds the configured maximum size.');
        }

        $content = File::get($path);

        try {
            $object = json_decode($content, false, 512, JSON_THROW_ON_ERROR);
            $transcript = json_decode($content, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $exception) {
            throw new InvalidTranscriptException('Transcript is not valid JSON.', previous: $exception);
        }

        if (! is_object($object) || ! is_array($transcript)) {
            throw new InvalidTranscriptException('Transcript must be a JSON object.');
        }

        if (! property_exists($object, 'runtime') || ! is_object($object->runtime)) {
            throw new InvalidTranscriptException('Transcript runtime must be an object.');
        }

        if (! property_exists($object, 'segments') || ! is_array($object->segments)) {
            throw new InvalidTranscriptException('Transcript segments must be an array.');
        }

        foreach ($object->segments as $index => $segment) {
            if (! is_object($segment)) {
                throw new InvalidTranscriptException("Transcript segment {$index} must be an object.");
            }
        }

        $this->validateTopLevel($transcript);

        $maximumSegments = min(
            100_000,
            (int) config('services.worker.artifacts.transcript.max_segments', 100_000),
        );

        if (count($transcript['segments']) > $maximumSegments) {
            throw new InvalidTranscriptException('Transcript contains too many segments.');
        }

        $segments = [];
        foreach ($transcript['segments'] as $index => $segment) {
            if (! is_array($segment)) {
                throw new InvalidTranscriptException("Transcript segment {$index} must be an object.");
            }

            $start = $this->finiteNumber($segment['start'] ?? null, "segment {$index} start");
            $end = $this->finiteNumber($segment['end'] ?? null, "segment {$index} end");

            if ($start < 0 || $end < $start) {
                throw new InvalidTranscriptException("Transcript segment {$index} has invalid timestamps.");
            }

            if (! isset($segment['text']) || ! is_string($segment['text'])) {
                throw new InvalidTranscriptException("Transcript segment {$index} text must be a string.");
            }

            $text = trim($segment['text']);
            $maximumTextLength = (int) config('services.worker.artifacts.transcript.max_text_length', 10_000);
            if ($text === '' || mb_strlen($text) > $maximumTextLength) {
                throw new InvalidTranscriptException("Transcript segment {$index} text is empty or too long.");
            }

            $speaker = array_key_exists('speaker', $segment) ? $segment['speaker'] : 'Unknown';
            $maximumSpeakerLength = (int) config('services.worker.artifacts.transcript.max_speaker_length', 255);
            if ($speaker !== null && (! is_string($speaker) || mb_strlen(trim($speaker)) > $maximumSpeakerLength)) {
                throw new InvalidTranscriptException("Transcript segment {$index} speaker is invalid.");
            }
            $speaker = is_string($speaker) ? trim($speaker) : null;

            $hasConfidence = array_key_exists('confidence', $segment) && $segment['confidence'] !== null;
            $confidence = $hasConfidence
                ? $this->finiteNumber($segment['confidence'], "segment {$index} confidence")
                : null;
            if ($confidence !== null && ($confidence < 0 || $confidence > 1)) {
                throw new InvalidTranscriptException("Transcript segment {$index} confidence is out of range.");
            }

            $segments[] = [
                'speaker' => $speaker,
                'text' => $text,
                'start' => $start,
                'end' => $end,
                'confidence' => $confidence,
                'has_confidence' => $hasConfidence,
                '_index' => $index,
            ];
        }

        usort($segments, fn (array $left, array $right): int => [
            $left['start'],
            $left['end'],
            $left['_index'],
        ] <=> [
            $right['start'],
            $right['end'],
            $right['_index'],
        ]);

        return array_map(function (array $segment): array {
            unset($segment['_index']);

            return $segment;
        }, $segments);
    }

    /**
     * @param  array<string, mixed>  $transcript
     */
    private function validateTopLevel(array $transcript): void
    {
        foreach (['driver', 'model', 'language'] as $field) {
            if (! isset($transcript[$field])
                || ! is_string($transcript[$field])
                || trim($transcript[$field]) === ''
                || mb_strlen($transcript[$field]) > 255) {
                throw new InvalidTranscriptException("Transcript {$field} is missing or invalid.");
            }
        }

        $duration = $this->finiteNumber($transcript['duration'] ?? null, 'duration');
        if ($duration < 0) {
            throw new InvalidTranscriptException('Transcript duration cannot be negative.');
        }

        if (! array_key_exists('language_probability', $transcript)) {
            throw new InvalidTranscriptException('Transcript language probability is missing.');
        }

        if ($transcript['language_probability'] !== null) {
            $probability = $this->finiteNumber($transcript['language_probability'], 'language probability');
            if ($probability < 0 || $probability > 1) {
                throw new InvalidTranscriptException('Transcript language probability is out of range.');
            }
        }

        if (! array_key_exists('runtime', $transcript) || ! is_array($transcript['runtime'])) {
            throw new InvalidTranscriptException('Transcript runtime must be an object.');
        }

        if (! array_key_exists('segments', $transcript) || ! is_array($transcript['segments'])) {
            throw new InvalidTranscriptException('Transcript segments must be an array.');
        }
    }

    private function finiteNumber(mixed $value, string $field): float
    {
        if (! is_int($value) && ! is_float($value)) {
            throw new InvalidTranscriptException("Transcript {$field} must be numeric.");
        }

        $number = (float) $value;
        if (! is_finite($number)) {
            throw new InvalidTranscriptException("Transcript {$field} must be finite.");
        }

        return $number;
    }

    /**
     * @param  list<array{speaker: ?string, text: string, start: float, end: float, confidence: ?float, has_confidence: bool}>  $segments
     */
    private function replaceRows(Meeting $meeting, array $segments): int
    {
        Transcription::where('meeting_id', $meeting->id)->delete();

        foreach ($segments as $segment) {
            $attributes = [
                'meeting_id' => $meeting->id,
                'speaker' => $segment['speaker'],
                'text' => $segment['text'],
                'start_time' => $segment['start'],
                'end_time' => $segment['end'],
            ];

            if ($segment['has_confidence']) {
                $attributes['confidence'] = $segment['confidence'];
            }

            Transcription::create($attributes);
        }

        return count($segments);
    }
}
