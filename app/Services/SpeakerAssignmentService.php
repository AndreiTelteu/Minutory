<?php

namespace App\Services;

use App\Models\Meeting;

class SpeakerAssignmentService
{
    /**
     * Apply the speaker with the largest temporal overlap to every transcript segment.
     * This intentionally never changes ASR text or timestamps. Uncovered segments keep
     * their current value: a partial diarization artifact must not erase known labels.
     *
     * @param  list<array{start: float, end: float, speaker: string}>  $turns
     */
    public function apply(Meeting $meeting, array $turns): int
    {
        $updated = 0;
        foreach ($meeting->transcriptions()->cursor() as $segment) {
            if ($segment->person_id !== null) {
                continue;
            }

            /** @var array<string, float> $durations */
            $durations = [];
            foreach ($turns as $turn) {
                $overlap = max(0.0, min((float) $segment->end_time, $turn['end']) - max((float) $segment->start_time, $turn['start']));
                if ($overlap > 0) {
                    $durations[$turn['speaker']] = ($durations[$turn['speaker']] ?? 0.0) + $overlap;
                }
            }

            if ($durations === []) {
                continue;
            }
            uksort($durations, fn (string $left, string $right): int => $durations[$right] <=> $durations[$left] ?: $left <=> $right);
            $speaker = array_key_first($durations);
            if ($speaker !== null && $segment->detected_speaker !== $speaker) {
                $segment->update([
                    'detected_speaker' => $speaker,
                    'speaker' => $speaker,
                ]);
                $updated++;
            }
        }

        return $updated;
    }
}
