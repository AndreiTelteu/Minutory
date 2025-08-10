<?php

namespace App\Tools;

use App\Models\Transcription;

class MeetingSearchTool
{
    public static function search(array $parameters): array
    {
        $query = $parameters['query'] ?? '';
        $clientId = $parameters['client_id'] ?? null;
        $speaker = $parameters['speaker'] ?? null;
        $limit = $parameters['limit'] ?? 10;

        if (empty($query)) {
            return [
                'error' => 'Search query cannot be empty'
            ];
        }

        try {
            $results = Transcription::query()
                ->with(['meeting.client'])
                ->where('text', 'like', "%{$query}%")
                ->when($clientId, function ($q) use ($clientId) {
                    return $q->whereHas('meeting', function ($q) use ($clientId) {
                        $q->where('client_id', $clientId);
                    });
                })
                ->when($speaker, function ($q) use ($speaker) {
                    return $q->where('speaker', 'like', "%{$speaker}%");
                })
                ->orderBy('start_time', 'asc')
                ->limit($limit)
                ->get()
                ->map(function ($transcription) use ($query) {
                    // Highlight the search term in the text
                    $highlightedText = str_ireplace(
                        $query,
                        "**{$query}**",
                        $transcription->text
                    );

                    return [
                        'meeting_id' => $transcription->meeting->id,
                        'meeting_title' => $transcription->meeting->title,
                        'client_name' => $transcription->meeting->client->name,
                        'speaker' => $transcription->speaker,
                        'text' => $highlightedText,
                        'timestamp' => (float) $transcription->start_time,
                        'formatted_timestamp' => self::formatTimestamp($transcription->start_time),
                        'confidence' => $transcription->confidence,
                        'meeting_url' => route('meetings.show', $transcription->meeting->id)
                    ];
                })
                ->toArray();

            return [
                'results' => $results,
                'total_found' => count($results),
                'search_query' => $query,
                'client_filter' => $clientId,
                'speaker_filter' => $speaker
            ];

        } catch (\Exception $e) {
            return [
                'error' => 'Search failed: ' . $e->getMessage()
            ];
        }
    }

    private static function formatTimestamp(float $seconds): string
    {
        $hours = floor($seconds / 3600);
        $minutes = floor(($seconds % 3600) / 60);
        $seconds = floor($seconds % 60);

        if ($hours > 0) {
            return sprintf('%02d:%02d:%02d', $hours, $minutes, $seconds);
        }

        return sprintf('%02d:%02d', $minutes, $seconds);
    }
}