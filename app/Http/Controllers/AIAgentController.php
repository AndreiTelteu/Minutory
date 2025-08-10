<?php

namespace App\Http\Controllers;

use App\Tools\MeetingSearchTool;
use App\Tools\PrismMeetingSearchTool;
use Prism\Prism\ValueObjects\Messages\UserMessage;
use Prism\Prism\ValueObjects\Messages\AssistantMessage;
use Prism\Prism\ValueObjects\Messages\SystemMessage;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Inertia\Inertia;
use Prism\Prism\Enums\Provider;
use Prism\Prism\Prism;

class AIAgentController extends Controller
{
    public function index()
    {
        return Inertia::render('AI/Chat');
    }

    public function chat(Request $request)
    {
        $request->validate([
            'message' => 'required|string|max:1000',
            'conversation_history' => 'array'
        ]);

        try {
            // Build conversation history
            $messages = [];
            
            // System message to set context
            $messages[] = new SystemMessage(
                'You are an AI assistant for a meeting transcription platform. ' .
                'You help users search through their meeting transcriptions and find specific information. ' .
                'When users ask about meeting content, use the search_meetings tool to find relevant information. ' .
                'Always provide helpful context about the meetings and include timestamps when available. ' .
                'Be conversational and helpful in your responses.'
            );

            // Add conversation history
            if ($request->has('conversation_history')) {
                foreach ($request->conversation_history as $msg) {
                    if ($msg['role'] === 'user') {
                        $messages[] = new UserMessage($msg['content']);
                    } elseif ($msg['role'] === 'assistant') {
                        $messages[] = new AssistantMessage($msg['content']);
                    }
                }
            }

            // Add current user message
            $messages[] = new UserMessage($request->message);

            // Make the AI request with tools
            $response = Prism::text()
                ->using(Provider::OpenRouter, 'openai/gpt-oss-120b')
                ->withMessages($messages)
                ->withTools([new PrismMeetingSearchTool()])
                ->generate();

            return response()->json([
                'success' => true,
                'response' => $response->text,
                'tool_calls' => array_map(function ($toolCall) {
                    return [
                        'name' => $toolCall->name ?? null,
                        'arguments' => method_exists($toolCall, 'arguments') ? $toolCall->arguments() : null,
                    ];
                }, is_array($response->toolCalls ?? null) ? $response->toolCalls : [])
            ]);

        } catch (\Exception $e) {
            Log::error('AI Chat Error: ' . $e->getMessage(), [
                'message' => $request->message,
                'trace' => $e->getTraceAsString()
            ]);

            return response()->json([
                'success' => false,
                'error' => 'I apologize, but I encountered an error processing your request. Please try again.'
            ], 500);
        }
    }

    public function search(Request $request)
    {
        $request->validate([
            'query' => 'present|nullable|string|max:500',
            'client_id' => 'nullable|integer|exists:clients,id',
            'speaker' => 'nullable|string|max:255',
            'limit' => 'nullable|integer|min:1|max:50'
        ]);

        // Handle empty query at controller level for better UX
        $query = $request->input('query', '');
        if (empty(trim($query))) {
            return response()->json([
                'success' => true,
                'data' => [
                    'error' => 'Search query cannot be empty'
                ]
            ]);
        }

        try {
            $result = MeetingSearchTool::search($request->only(['query', 'client_id', 'speaker', 'limit']));

            return response()->json([
                'success' => true,
                'data' => $result
            ]);

        } catch (\Exception $e) {
            Log::error('Direct Search Error: ' . $e->getMessage(), [
                'query' => $request->query,
                'trace' => $e->getTraceAsString()
            ]);

            return response()->json([
                'success' => false,
                'error' => 'Search failed. Please try again.'
            ], 500);
        }
    }
}