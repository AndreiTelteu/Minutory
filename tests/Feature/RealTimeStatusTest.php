<?php

use App\Models\Client;
use App\Models\Meeting;

it('calculates elapsed time correctly for processing meetings', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'processing_started_at' => now()->subMinutes(2),
        'duration' => 1800, // 30 minutes
        'estimated_processing_time' => 30 // 30 seconds
    ]);

    expect($meeting->elapsed_time)->toBeGreaterThan(100); // At least 100 seconds
    expect($meeting->formatted_elapsed_time)->toMatch('/\d+:\d{2}/');
    expect($meeting->processing_progress)->toBeGreaterThan(0);
});

it('calculates queue progress for pending meetings', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'pending',
        'uploaded_at' => now()->subSeconds(15),
        'estimated_processing_time' => 30
    ]);

    expect($meeting->queue_progress)->toBeGreaterThan(0);
    expect($meeting->queue_progress)->toBeLessThanOrEqual(100);
});

it('returns null progress for completed meetings', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'completed',
        'processing_started_at' => now()->subMinutes(5),
        'processing_completed_at' => now()->subMinutes(2)
    ]);

    expect($meeting->processing_progress)->toBeNull();
    expect($meeting->queue_progress)->toBeNull();
    expect($meeting->elapsed_time)->toBeGreaterThan(0); // Should still show elapsed time
});

it('handles edge cases in progress calculations', function () {
    $client = Client::factory()->create();
    
    // Meeting without processing_started_at
    $meeting1 = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'processing_started_at' => null
    ]);
    
    expect($meeting1->elapsed_time)->toBeNull();
    expect($meeting1->processing_progress)->toBeNull();
    
    // Meeting without duration
    $meeting2 = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'processing_started_at' => now()->subMinutes(1),
        'duration' => null
    ]);
    
    expect($meeting2->processing_progress)->toBeNull();
});

it('formats time correctly', function () {
    $client = Client::factory()->create();
    $meeting = Meeting::factory()->create([
        'client_id' => $client->id,
        'status' => 'processing',
        'processing_started_at' => now()->subSeconds(125), // 2 minutes 5 seconds
        'duration' => 3600 // 1 hour
    ]);

    expect($meeting->formatted_elapsed_time)->toBe('2:05');
    
    // Test estimated remaining time formatting
    expect($meeting->formatted_estimated_remaining_time)->toMatch('/\d+:\d{2}/');
});