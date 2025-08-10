<?php

namespace App\Jobs;

use App\Models\Meeting;
use App\Models\Transcription;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class TranscribeMeetingJob implements ShouldQueue
{
    use Queueable, InteractsWithQueue, SerializesModels;

    public $timeout = 3600; // 1 hour timeout
    public $tries = 3;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public Meeting $meeting
    ) {}

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        try {
            Log::info("Starting transcription for meeting {$this->meeting->id}");

            // Update meeting status to processing
            $this->meeting->update([
                'status' => 'processing',
                'processing_started_at' => now(),
            ]);

            // Simulate transcription processing time based on video duration
            // For development, we'll use a shorter time (1 second per minute of video)
            $processingTimeSeconds = max(10, ($this->meeting->duration ?? 300) / 60);
            
            Log::info("Simulating transcription processing for {$processingTimeSeconds} seconds");
            
            // Sleep to simulate processing time
            sleep((int) $processingTimeSeconds);

            // Generate fake transcription data
            $this->generateFakeTranscription();

            // Update meeting status to completed
            $this->meeting->update([
                'status' => 'completed',
                'processing_completed_at' => now(),
            ]);

            Log::info("Completed transcription for meeting {$this->meeting->id}");

        } catch (\Exception $e) {
            Log::error("Transcription failed for meeting {$this->meeting->id}: " . $e->getMessage());
            
            // Update meeting status to failed
            $this->meeting->update([
                'status' => 'failed',
                'processing_completed_at' => now(),
            ]);

            throw $e;
        }
    }

    /**
     * Generate fake transcription data using Laravel Faker
     */
    private function generateFakeTranscription(): void
    {
        $faker = fake();
        $duration = $this->meeting->duration ?? 1800; // Default 30 minutes
        $speakers = ['Speaker A', 'Speaker B', 'Speaker C'];
        
        // Generate transcription segments
        $currentTime = 0;
        $segmentCount = rand(20, 50); // Random number of segments
        
        for ($i = 0; $i < $segmentCount; $i++) {
            $segmentDuration = rand(5, 30); // 5-30 seconds per segment
            $endTime = min($currentTime + $segmentDuration, $duration);
            
            // Generate realistic meeting content
            $meetingPhrases = [
                "Let's discuss the quarterly results and our performance metrics.",
                "I think we should focus on improving customer satisfaction scores.",
                "The budget allocation for next quarter needs to be reviewed.",
                "Can we schedule a follow-up meeting to discuss the implementation details?",
                "I agree with the proposed timeline, but we might need additional resources.",
                "The client feedback has been overwhelmingly positive so far.",
                "We need to address the technical challenges before moving forward.",
                "Let's table this discussion and revisit it in our next meeting.",
                "The marketing campaign results exceeded our expectations.",
                "I'll send out the action items and meeting notes after this call.",
                "We should consider the long-term implications of this decision.",
                "The development team has made significant progress this sprint.",
                "Let's review the key performance indicators for this project.",
                "I think we need to involve the stakeholders in this decision.",
                "The deadline is tight, but I believe we can deliver on time."
            ];
            
            Transcription::create([
                'meeting_id' => $this->meeting->id,
                'speaker' => $speakers[array_rand($speakers)],
                'text' => $faker->randomElement($meetingPhrases),
                'start_time' => $currentTime,
                'end_time' => $endTime,
                'confidence' => $faker->randomFloat(2, 0.85, 0.99), // High confidence scores
            ]);
            
            $currentTime = $endTime;
            
            // Stop if we've reached the video duration
            if ($currentTime >= $duration) {
                break;
            }
        }
        
        Log::info("Generated {$segmentCount} transcription segments for meeting {$this->meeting->id}");
    }

    /**
     * Handle a job failure.
     */
    public function failed(\Throwable $exception): void
    {
        Log::error("TranscribeMeetingJob failed for meeting {$this->meeting->id}: " . $exception->getMessage());
        
        // Update meeting status to failed
        $this->meeting->update([
            'status' => 'failed',
            'processing_completed_at' => now(),
        ]);
    }
}
