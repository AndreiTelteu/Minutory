<?php

namespace App\Jobs;

use App\Models\Meeting;
use App\Models\Transcription;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;
use Symfony\Component\Process\Process;
use Symfony\Component\Process\Exception\ProcessFailedException;

class TranscribeMeetingJob implements ShouldQueue
{
    use Queueable, InteractsWithQueue, SerializesModels;

    public $timeout = 3600; // 1 hour timeout
    public $tries = 1;

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
    
            // Resolve paths
            $meetingId = $this->meeting->id;
            $projectRoot = base_path();
            $storageDir = $projectRoot . DIRECTORY_SEPARATOR . 'storage' . DIRECTORY_SEPARATOR . $meetingId;
            $wavPath = $storageDir . DIRECTORY_SEPARATOR . 'audio.wav';
            $transcriptPath = $storageDir . DIRECTORY_SEPARATOR . 'transcript.json';
    
            // Ensure storage/{meeting_id} directory exists
            if (!File::exists($storageDir)) {
                File::makeDirectory($storageDir, 0755, true);
            }
    
                                    // Resolve input video path from the public storage disk
                                    $videoPath = Storage::disk('public')->path($this->meeting->video_path);
                        
                                    if (!File::exists($videoPath)) {
                                        throw new \RuntimeException("Video file not found at path: {$videoPath}");
                                    }
            
                        // Build docker-friendly mount paths
                        $inDirHost = dirname($videoPath);
                        $inFileBase = basename($videoPath);
                        $outDirHost = $storageDir;
    
            $inDirDocker = $this->dockerPath($inDirHost);
            $outDirDocker = $this->dockerPath($outDirHost);
    
            // Docker image names (allow override via env)
            $ffmpegImage = config('services.ffmpeg.image', 'jrottenberg/ffmpeg:latest');
            $scriberrImage = config('services.scriberr.image', 'scriberr-local:latest');
    
            // 1) Convert video to WAV using ffmpeg in Docker
            $ffmpegCmd = sprintf(
                'docker run --rm -v "%s:/in/" -v "%s:/out" %s -hide_banner -y -i "/in/%s" -vn -acodec pcm_s16le -ar 16000 -ac 1 "/out/audio.wav"',
                $inDirDocker,
                $outDirDocker,
                escapeshellarg($ffmpegImage),
                str_replace('"', '\"', $inFileBase)
            );
    
            Log::info("Running ffmpeg docker command for meeting {$meetingId}: {$ffmpegCmd}");
            $this->runShell($ffmpegCmd, $this->timeout - 60); // leave buffer
    
            if (!File::exists($wavPath)) {
                throw new \RuntimeException("WAV conversion did not produce expected file at: {$wavPath}");
            }
    
            // 2) Prepare transcript file and run transcription container
            if (!File::exists($transcriptPath)) {
                // Equivalent to touch
                File::put($transcriptPath, '');
            }
    
            $wavMount = $this->dockerPath($wavPath);
            $transcriptMount = $this->dockerPath($transcriptPath);
    
            $scriberrCmd = sprintf(
                'docker run --rm -v "%s:/input.wav" -v "%s:/transcript.json" %s transcribe.py --audio-file /input.wav --model-size medium --output-file /transcript.json --threads 8 --language ro --diarize --align --device cpu --compute-type int8',
                $wavMount,
                $transcriptMount,
                escapeshellarg($scriberrImage)
            );
    
            Log::info("Running transcription docker command for meeting {$meetingId}");
            $this->runShell($scriberrCmd, $this->timeout - 120); // leave more buffer
    
            // Optional: If you want to read transcript and persist segments later, do it here.
    
            // Update meeting status to completed
            $this->meeting->update([
                'status' => 'completed',
                'processing_completed_at' => now(),
            ]);
    
            Log::info("Completed transcription for meeting {$this->meeting->id} -> transcript at {$transcriptPath}");
        } catch (\Throwable $e) {
            Log::error("Transcription failed for meeting {$this->meeting->id}: " . $e->getMessage());
    
            // Update meeting status to failed
            $this->meeting->update([
                'status' => 'failed',
                'processing_completed_at' => now(),
            ]);
    
            throw $e;
        }
    }
    
    private function processPathForLocalTesting(string $path): string
    {
        $path = str_replace('E:\\', '/mnt/e/', $path);
        return $path;
    }

    /**
     * Generate fake transcription data using Laravel Faker
     * Kept for potential fallback/testing; currently unused by handle()
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
     * Convert a host path to a Docker-friendly path (uses forward slashes).
     */
    private function dockerPath(string $path): string
    {
        $real = realpath($path) ?: $path;
        $real = $this->processPathForLocalTesting($real);
        return str_replace('\\', '/', $real);
    }
    
    /**
     * Run a shell command with logging and error handling.
     *
     * @throws \RuntimeException on non-zero exit
     */
    private function runShell(string $command, ?int $timeoutSeconds = null): void
    {
        $process = Process::fromShellCommandline($command, base_path(), null, null, $timeoutSeconds);
        $process->run(function ($type, $buffer) {
            if ($type === Process::OUT) {
                Log::info(trim($buffer));
            } else {
                Log::warning(trim($buffer));
            }
        });
    
        if (!$process->isSuccessful()) {
            $exitCode = $process->getExitCode();
            $err = $process->getErrorOutput() ?: $process->getOutput();
            throw new \RuntimeException("Command failed (exit {$exitCode}): {$err}");
        }
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
