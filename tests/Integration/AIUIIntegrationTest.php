<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Support\Facades\Http;

use function Pest\Laravel\get;
use function Pest\Laravel\post;

describe('AI UI Integration', function () {
    beforeEach(function () {
        $this->client = Client::factory()->create(['name' => 'Test Client']);
        $this->meeting = Meeting::factory()->create([
            'client_id' => $this->client->id,
            'title' => 'Test Meeting',
            'transcript' => 'This is a test transcript about project planning.',
            'summary' => 'Meeting summary about project planning.',
            'status' => 'completed',
        ]);
    });

    describe('AI Chat Page', function () {
        it('displays AI chat page', function () {
            $response = get(route('ai.chat'));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('AI/Chat')
            );
        });

        it('sends chat message successfully', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'This is a test AI response.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            $response = post(route('ai.chat.send'), [
                'message' => 'What was discussed in the recent meetings?',
            ]);

            $response->assertStatus(200);
            $response->assertJson([
                'response' => 'This is a test AI response.',
            ]);
        });

        it('handles empty message', function () {
            $response = post(route('ai.chat.send'), [
                'message' => '',
            ]);

            $response->assertSessionHasErrors(['message']);
        });

        it('handles AI service error gracefully', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([], 500),
            ]);

            $response = post(route('ai.chat.send'), [
                'message' => 'Test message',
            ]);

            $response->assertStatus(500);
            $response->assertJson([
                'error' => 'Failed to get AI response',
            ]);
        });
    });

    describe('AI Search Functionality', function () {
        it('searches meetings successfully', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'Based on the search, I found information about project planning.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            $response = post(route('ai.search'), [
                'query' => 'project planning',
            ]);

            $response->assertStatus(200);
            $response->assertJson([
                'response' => 'Based on the search, I found information about project planning.',
            ]);
        });

        it('validates search query', function () {
            $response = post(route('ai.search'), [
                'query' => '',
            ]);

            $response->assertSessionHasErrors(['query']);
        });

        it('includes relevant meeting data in search context', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'Found relevant information in Test Meeting.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            $response = post(route('ai.search'), [
                'query' => 'project',
            ]);

            $response->assertStatus(200);

            // Verify that the AI service was called with meeting context
            Http::assertSent(function ($request) {
                $body = json_decode($request->body(), true);

                return str_contains($body['messages'][0]['content'], 'Test Meeting') &&
                       str_contains($body['messages'][0]['content'], 'project planning');
            });
        });

        it('handles search with no relevant meetings', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'No relevant information found in your meetings.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            $response = post(route('ai.search'), [
                'query' => 'irrelevant topic',
            ]);

            $response->assertStatus(200);
            $response->assertJson([
                'response' => 'No relevant information found in your meetings.',
            ]);
        });
    });

    describe('AI Context Integration', function () {
        it('includes meeting transcripts in AI context', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'Based on your meetings, here is the information.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            post(route('ai.chat.send'), [
                'message' => 'What was discussed?',
            ]);

            Http::assertSent(function ($request) {
                $body = json_decode($request->body(), true);

                return str_contains($body['messages'][0]['content'], 'This is a test transcript');
            });
        });

        it('includes meeting summaries in AI context', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'Based on your meeting summaries.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            post(route('ai.chat.send'), [
                'message' => 'Summarize recent meetings',
            ]);

            Http::assertSent(function ($request) {
                $body = json_decode($request->body(), true);

                return str_contains($body['messages'][0]['content'], 'Meeting summary about project planning');
            });
        });

        it('excludes incomplete meetings from context', function () {
            $incompleteMeeting = Meeting::factory()->create([
                'client_id' => $this->client->id,
                'title' => 'Incomplete Meeting',
                'status' => 'pending',
                'transcript' => null,
                'summary' => null,
            ]);

            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'Response based on available data.',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            post(route('ai.chat.send'), [
                'message' => 'What meetings do you have?',
            ]);

            Http::assertSent(function ($request) {
                $body = json_decode($request->body(), true);

                return str_contains($body['messages'][0]['content'], 'Test Meeting') &&
                       ! str_contains($body['messages'][0]['content'], 'Incomplete Meeting');
            });
        });
    });

    describe('AI Response Formatting', function () {
        it('formats AI responses properly', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => "Here's what I found:\n\n1. First point\n2. Second point",
                            ],
                        ],
                    ],
                ], 200),
            ]);

            $response = post(route('ai.chat.send'), [
                'message' => 'Give me a summary',
            ]);

            $response->assertStatus(200);
            $response->assertJson([
                'response' => "Here's what I found:\n\n1. First point\n2. Second point",
            ]);
        });

        it('handles special characters in AI responses', function () {
            Http::fake([
                'api.openai.com/*' => Http::response([
                    'choices' => [
                        [
                            'message' => [
                                'content' => 'Response with "quotes" and special chars: @#$%',
                            ],
                        ],
                    ],
                ], 200),
            ]);

            $response = post(route('ai.chat.send'), [
                'message' => 'Test message',
            ]);

            $response->assertStatus(200);
            $response->assertJson([
                'response' => 'Response with "quotes" and special chars: @#$%',
            ]);
        });
    });
});
