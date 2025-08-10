<?php

namespace Database\Seeders;

use App\Models\Client;
use Illuminate\Database\Seeder;

class ClientSeeder extends Seeder
{
    /**
     * Run the database seeder.
     */
    public function run(): void
    {
        Client::factory()->create([
            'name' => 'Acme Corporation',
            'email' => 'contact@acme.com',
            'company' => 'Acme Corp',
            'phone' => '+1 (555) 123-4567'
        ]);

        Client::factory()->create([
            'name' => 'John Smith',
            'email' => 'john@example.com',
            'company' => 'Smith Consulting',
            'phone' => '+1 (555) 987-6543'
        ]);

        Client::factory()->create([
            'name' => 'Sarah Johnson',
            'email' => 'sarah@techstartup.com',
            'company' => 'Tech Startup Inc',
            'phone' => '+1 (555) 456-7890'
        ]);

        // Create a client without optional fields
        Client::factory()->create([
            'name' => 'Basic Client',
            'email' => null,
            'company' => null,
            'phone' => null
        ]);
    }
}