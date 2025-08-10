<?php

namespace Database\Factories;

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\Meeting>
 */
class MeetingFactory extends Factory
{
    protected $model = Meeting::class;

    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $duration = fake()->numberBetween(300, 3600); // 5 minutes to 1 hour
        $estimatedProcessingTime = max(10, $duration / 60); // 1 second per minute, minimum 10 seconds
        
        return [
            'client_id' => Client::factory(),
            'title' => fake()->sentence(3),
            'video_path' => 'meetings/' . fake()->numberBetween(1, 100) . '/' . fake()->numberBetween(1, 1000) . '/video.mp4',
            'status' => fake()->randomElement(['pending', 'processing', 'completed', 'failed']),
            'duration' => $duration,
            'estimated_processing_time' => (int) $estimatedProcessingTime,
            'uploaded_at' => fake()->dateTimeBetween('-1 month', 'now'),
            'processing_started_at' => null,
            'processing_completed_at' => null,
        ];
    }

    /**
     * Indicate that the meeting is pending.
     */
    public function pending(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => 'pending',
            'processing_started_at' => null,
            'processing_completed_at' => null,
        ]);
    }

    /**
     * Indicate that the meeting is processing.
     */
    public function processing(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => 'processing',
            'processing_started_at' => fake()->dateTimeBetween('-1 hour', 'now'),
            'processing_completed_at' => null,
        ]);
    }

    /**
     * Indicate that the meeting is completed.
     */
    public function completed(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => 'completed',
            'processing_started_at' => fake()->dateTimeBetween('-2 hours', '-1 hour'),
            'processing_completed_at' => fake()->dateTimeBetween('-1 hour', 'now'),
        ]);
    }

    /**
     * Indicate that the meeting has failed.
     */
    public function failed(): static
    {
        return $this->state(fn (array $attributes) => [
            'status' => 'failed',
            'processing_started_at' => fake()->dateTimeBetween('-2 hours', '-1 hour'),
            'processing_completed_at' => null,
        ]);
    }
}