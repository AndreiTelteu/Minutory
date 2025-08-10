<?php

namespace Database\Factories;

use App\Models\Meeting;
use App\Models\Transcription;
use Illuminate\Database\Eloquent\Factories\Factory;

/**
 * @extends \Illuminate\Database\Eloquent\Factories\Factory<\App\Models\Transcription>
 */
class TranscriptionFactory extends Factory
{
    protected $model = Transcription::class;

    /**
     * Define the model's default state.
     *
     * @return array<string, mixed>
     */
    public function definition(): array
    {
        $speakers = ['John Smith', 'Sarah Johnson', 'Mike Davis', 'Emily Chen', 'David Wilson', 'Lisa Brown'];
        $startTime = fake()->randomFloat(3, 0, 3000); // Random start time up to 50 minutes
        $duration = fake()->randomFloat(3, 2, 30); // Duration between 2-30 seconds
        
        return [
            'meeting_id' => Meeting::factory(),
            'speaker' => fake()->randomElement($speakers),
            'text' => fake()->paragraph(fake()->numberBetween(1, 4)),
            'start_time' => $startTime,
            'end_time' => $startTime + $duration,
            'confidence' => fake()->randomFloat(2, 0.6, 1.0), // Confidence between 60-100%
        ];
    }

    /**
     * Create transcriptions for a specific meeting with sequential timing.
     */
    public function forMeeting(Meeting $meeting): static
    {
        return $this->state(fn (array $attributes) => [
            'meeting_id' => $meeting->id,
        ]);
    }

    /**
     * Create a sequence of transcriptions with proper timing.
     */
    public function sequence(float $startTime = 0): static
    {
        static $currentTime = 0;
        
        if ($startTime > 0) {
            $currentTime = $startTime;
        }
        
        $duration = fake()->randomFloat(3, 3, 15); // 3-15 seconds per segment
        $segmentStartTime = $currentTime;
        $segmentEndTime = $currentTime + $duration;
        
        // Add small gap between segments
        $currentTime = $segmentEndTime + fake()->randomFloat(3, 0.5, 2);
        
        return $this->state(fn (array $attributes) => [
            'start_time' => $segmentStartTime,
            'end_time' => $segmentEndTime,
        ]);
    }

    /**
     * Create transcription with high confidence.
     */
    public function highConfidence(): static
    {
        return $this->state(fn (array $attributes) => [
            'confidence' => fake()->randomFloat(2, 0.9, 1.0),
        ]);
    }

    /**
     * Create transcription with low confidence.
     */
    public function lowConfidence(): static
    {
        return $this->state(fn (array $attributes) => [
            'confidence' => fake()->randomFloat(2, 0.5, 0.7),
        ]);
    }
}