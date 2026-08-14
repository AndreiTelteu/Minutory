<?php

namespace App\Services;

use App\Exceptions\InvalidTranscriptException;
use Illuminate\Support\Facades\File;

class SpeakerTurnsImporter
{
    /** @return list<array{start: float, end: float, speaker: string}> */
    public function validateFile(string $path): array
    {
        if (! File::isFile($path)) {
            throw new InvalidTranscriptException('Speaker identification file was not found.');
        }

        $content = File::get($path);
        try {
            $document = json_decode($content, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $exception) {
            throw new InvalidTranscriptException('Speaker identification file is not valid JSON.', previous: $exception);
        }

        if (! is_array($document) || ! is_array($document['turns'] ?? null)) {
            throw new InvalidTranscriptException('Speaker identification file must contain a turns array.');
        }

        $turns = [];
        foreach ($document['turns'] as $index => $turn) {
            if (! is_array($turn)) {
                throw new InvalidTranscriptException("Speaker turn {$index} must be an object.");
            }
            $start = $this->finiteNumber($turn['start'] ?? null, "speaker turn {$index} start");
            $end = $this->finiteNumber($turn['end'] ?? null, "speaker turn {$index} end");
            $speaker = $turn['speaker'] ?? null;
            if ($start < 0 || $end < $start || $start > 9_999_999.999 || $end > 9_999_999.999) {
                throw new InvalidTranscriptException("Speaker turn {$index} has invalid timestamps.");
            }
            if (! is_string($speaker) || trim($speaker) === '' || mb_strlen(trim($speaker)) > 255) {
                throw new InvalidTranscriptException("Speaker turn {$index} speaker is invalid.");
            }
            $turns[] = ['start' => $start, 'end' => $end, 'speaker' => trim($speaker)];
        }

        usort($turns, fn (array $a, array $b): int => [$a['start'], $a['end'], $a['speaker']] <=> [$b['start'], $b['end'], $b['speaker']]);

        return $turns;
    }

    private function finiteNumber(mixed $value, string $field): float
    {
        if (! is_int($value) && ! is_float($value) || ! is_finite((float) $value)) {
            throw new InvalidTranscriptException("Speaker identification {$field} must be finite numeric.");
        }

        return (float) $value;
    }
}
