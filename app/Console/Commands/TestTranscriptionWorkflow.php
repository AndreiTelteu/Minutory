<?php

namespace App\Console\Commands;

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Console\Command;

class TestTranscriptionWorkflow extends Command
{
    /**
     * The name and signature of the console command.
     *
     * @var string
     */
    protected $signature = 'test:transcription-workflow';

    /**
     * The console command description.
     *
     * @var string
     */
    protected $description = 'Test the complete transcription workflow';

    /**
     * Execute the console command.
     */
    public function handle()
    {
        $this->info('Testing transcription workflow...');

        // Create a test client
        $client = Client::factory()->create([
            'name' => 'Test Client - ' . now()->format('H:i:s'),
            'email' => 'test-' . now()->timestamp . '@example.com'
        ]);
        $this->info("Created client: {$client->name}");

        // Create a test meeting
        $meeting = Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Test Meeting - Transcription Workflow',
            'status' => 'pending',
            'duration' => 120, // 2 minutes for quick testing
        ]);
        $this->info("Created meeting: {$meeting->title}");

        // Dispatch the transcription job
        $this->info('Dispatching transcription job...');
        TranscribeMeetingJob::dispatch($meeting);

        // Show initial status
        $meeting->refresh();
        $this->info("Meeting status: {$meeting->status}");

        $this->info('Job dispatched! Run "php artisan queue:work" to process it.');
        $this->info("You can check the meeting status at: /meetings/{$meeting->id}/status");
        
        return 0;
    }
}
