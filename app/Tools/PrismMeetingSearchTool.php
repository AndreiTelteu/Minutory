<?php

namespace App\Tools;

use Prism\Prism\Tool;

class PrismMeetingSearchTool extends Tool
{
    public function __construct()
    {
        parent::__construct();
        
        $this->as('search_meetings')
            ->for('Search through meeting transcriptions to find specific content, topics, or keywords')
            ->withStringParameter('query', 'The search query to find in meeting transcriptions', true)
            ->withStringParameter('client_id', 'Optional client ID to filter search results to specific client meetings', false)
            ->withStringParameter('speaker', 'Optional speaker name to filter results to specific speaker', false)
            ->withStringParameter('limit', 'Maximum number of results to return (default: 10)', false)
            ->using(function (string $query, $client_id = null, ?string $speaker = null, $limit = 10): string {
                $client_id = is_numeric($client_id) ? (int) $client_id : null;
                $limit = is_numeric($limit) ? max(1, min(50, (int) $limit)) : 10;

                $result = MeetingSearchTool::search([
                    'query' => $query,
                    'client_id' => $client_id,
                    'speaker' => $speaker,
                    'limit' => $limit
                ]);

                if (isset($result['error'])) {
                    return "Error: " . $result['error'];
                }

                if (empty($result['results'])) {
                    return "No results found for query: '{$query}'";
                }

                $output = "Found {$result['total_found']} results for '{$query}':\n\n";
                
                foreach ($result['results'] as $item) {
                    $output .= "**{$item['meeting_title']}** ({$item['client_name']})\n";
                    $output .= "Speaker: {$item['speaker']} at {$item['formatted_timestamp']}\n";
                    $output .= "Text: {$item['text']}\n";
                    $output .= "Link: {$item['meeting_url']}?t={$item['timestamp']}\n\n";
                }

                return $output;
            });
    }
}