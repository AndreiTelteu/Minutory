<?php

namespace Database\Seeders;

use App\Models\Meeting;
use Illuminate\Database\Console\Seeds\WithoutModelEvents;
use Illuminate\Database\Seeder;

class MeetingSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        // Create some meetings in different states
        Meeting::factory(3)->pending()->create();
        Meeting::factory(2)->processing()->create();
        Meeting::factory(3)->completed()->withTranscriptions()->create();
        Meeting::factory(1)->failed()->create();
        Meeting::factory(1)->completed()->create(); // Completed without transcriptions
    }
}
