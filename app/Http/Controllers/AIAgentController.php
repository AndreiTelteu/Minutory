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
            'conversation_history' => 'array|max:50' // Limit conversation history
        ], [
            'message.required' => 'Please enter a message.',
            'message.max' => 'Message cannot exceed 1000 characters.',
            'conversation_history.max' => 'Conversation history is too long.'
        ]);

        try {
            // Rate limiting check (basic implementation)
            $cacheKey = 'ai_chat_' . $request->ip();
            $requestCount = cache()->get($cacheKey, 0);
            
            if ($requestCount >= 10) { // 10 requests per minute
                return response()->json([
                    'success' => false,
                    'error' => 'Too many requests. Please wait a moment before sending another message.'
                ], 429);
            }
            
            cache()->put($cacheKey, $requestCount + 1, 60); // Increment for 1 minute

            // Build conversation history
            $messages = [];
            
            // System message to set context
            $messages[] = new SystemMessage(
                'You are an AI assistant for a meeting transcription platform. ' .
                'You help users search through their meeting transcriptions and find specific information. ' .
                'When users ask about meeting content, use the search_meetings tool to find relevant information. ' .
                'Always provide helpful context about the meetings and include timestamps when available. ' .
                'Be conversational and helpful in your responses. ' .
                'If you encounter any errors, explain them clearly and suggest alternatives.'
            );

            // Add conversation history with validation
            if ($request->has('conversation_history') && is_array($request->conversation_history)) {
                foreach ($request->conversation_history as $msg) {
                    if (!is_array($msg) || !isset($msg['role']) || !isset($msg['content'])) {
                        continue; // Skip invalid messages
                    }
                    
                    if ($msg['role'] === 'user') {
                        $messages[] = new UserMessage($msg['content']);
                    } elseif ($msg['role'] === 'assistant') {
                        $messages[] = new AssistantMessage($msg['content']);
                    }
                }
            }

            // Add current user message
            $messages[] = new UserMessage($request->message);

            // Make the AI request with tools and timeout
            $startTime = microtime(true);
            
            $response = Prism::text()
                ->using(Provider::OpenRouter, 'openai/gpt-oss-120b')
                ->withMessages($messages)
                ->withTools([new PrismMeetingSearchTool()])
                ->generate();

            $processingTime = microtime(true) - $startTime;

            // Log successful requests for monitoring
            Log::info('AI Chat Success', [
                'message_length' => strlen($request->message),
                'processing_time' => $processingTime,
                'response_length' => strlen($response->text ?? ''),
                'tool_calls_count' => count($response->toolCalls ?? [])
            ]);

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

        } catch (\Illuminate\Validation\ValidationException $e) {
            return response()->json([
                'success' => false,
                'error' => 'Invalid input: ' . $e->getMessage()
            ], 422);
        } catch (\Exception $e) {
            Log::error('AI Chat Error: ' . $e->getMessage(), [
                'message' => $request->message,
                'trace' => $e->getTraceAsString(),
                'ip' => $request->ip()
            ]);

            // Determine error type and provide appropriate response
            $errorMessage = 'I apologize, but I encountered an error processing your request.';
            $statusCode = 500;

            if (str_contains($e->getMessage(), 'timeout') || str_contains($e->getMessage(), 'timed out')) {
                $errorMessage = 'The request timed out. Please try again with a shorter message.';
                $statusCode = 408;
            } elseif (str_contains($e->getMessage(), 'rate limit') || str_contains($e->getMessage(), 'quota')) {
                $errorMessage = 'AI service is currently busy. Please try again in a few moments.';
                $statusCode = 429;
            } elseif (str_contains($e->getMessage(), 'network') || str_contains($e->getMessage(), 'connection')) {
                $errorMessage = 'Network error occurred. Please check your connection and try again.';
                $statusCode = 503;
            }

            return response()->json([
                'success' => false,
                'error' => $errorMessage
            ], $statusCode);
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