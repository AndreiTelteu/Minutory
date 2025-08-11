<?php

use App\Models\Client;
use App\Models\Meeting;

it('can complete the full client management workflow', function () {
    // Test client creation workflow
    $response = $this->get(route('clients.index'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => $page->component('Clients/Index'));

    // Create a new client
    $clientData = [
        'name' => 'Acme Corporation',
        'email' => 'contact@acme.com',
        'company' => 'Acme Corp',
        'phone' => '+1-555-123-4567'
    ];

    $response = $this->post(route('clients.store'), $clientData);
    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('success', 'Client created successfully.');
    
    $this->assertDatabaseHas('clients', $clientData);
    
    // Test client viewing
    $client = Client::where('email', 'contact@acme.com')->first();
    $response = $this->get(route('clients.show', $client));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Clients/Show')
             ->where('client.name', 'Acme Corporation')
    );

    // Test client editing
    $updateData = [
        'name' => 'Updated Acme Corporation',
        'email' => 'updated@acme.com',
        'company' => 'Updated Acme Corp',
        'phone' => '+1-555-987-6543'
    ];

    $response = $this->put(route('clients.update', $client), $updateData);
    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('success', 'Client updated successfully.');
    
    $this->assertDatabaseHas('clients', array_merge(['id' => $client->id], $updateData));

    // Test client deletion (should fail if client has meetings)
    Meeting::factory()->create(['client_id' => $client->id]);
    
    $response = $this->delete(route('clients.destroy', $client));
    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('error', 'Cannot delete client with existing meetings.');
    
    $this->assertDatabaseHas('clients', ['id' => $client->id]);
});

it('can view and edit client details')
    ->browse(function ($browser) {
        $client = Client::factory()->create([
            'name' => 'Test Client',
            'email' => 'test@example.com',
            'company' => 'Test Company',
            'phone' => '555-0123'
        ]);

        $browser->visit('/clients')
                ->assertSee($client->name)
                ->click("[data-testid=\"view-client-{$client->id}\"]")
                ->assertPathIs("/clients/{$client->id}")
                ->assertSee($client->name)
                ->assertSee($client->email)
                ->assertSee($client->company)
                ->click('[data-testid="edit-client-button"]')
                ->assertPathIs("/clients/{$client->id}/edit")
                ->clear('[data-testid="client-name"]')
                ->type('[data-testid="client-name"]', 'Updated Test Client')
                ->clear('[data-testid="client-email"]')
                ->type('[data-testid="client-email"]', 'updated@example.com')
                ->click('[data-testid="update-client-button"]')
                ->assertPathIs('/clients')
                ->assertSee('Client updated successfully')
                ->assertSee('Updated Test Client')
                ->assertSee('updated@example.com');
    });

it('can delete a client without meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create([
            'name' => 'Client to Delete',
            'email' => 'delete@example.com'
        ]);

        $browser->visit('/clients')
                ->assertSee($client->name)
                ->click("[data-testid=\"delete-client-{$client->id}\"]")
                ->assertDialogOpened('Are you sure you want to delete this client?')
                ->acceptDialog()
                ->assertSee('Client deleted successfully')
                ->assertDontSee($client->name);
    });

it('prevents deletion of client with meetings')
    ->browse(function ($browser) {
        $client = Client::factory()->create([
            'name' => 'Client with Meetings'
        ]);
        
        Meeting::factory()->create([
            'client_id' => $client->id,
            'title' => 'Important Meeting'
        ]);

        $browser->visit('/clients')
                ->assertSee($client->name)
                ->click("[data-testid=\"delete-client-{$client->id}\"]")
                ->assertDialogOpened('Are you sure you want to delete this client?')
                ->acceptDialog()
                ->assertSee('Cannot delete client with existing meetings')
                ->assertSee($client->name); // Client should still be visible
    });

it('validates client form fields')
    ->browse(function ($browser) {
        $browser->visit('/clients/create')
                ->click('[data-testid="save-client-button"]')
                ->assertSee('The name field is required')
                ->type('[data-testid="client-name"]', 'Test Client')
                ->type('[data-testid="client-email"]', 'invalid-email')
                ->click('[data-testid="save-client-button"]')
                ->assertSee('The email field must be a valid email address');
    });

it('shows client meeting count and allows filtering')
    ->browse(function ($browser) {
        $client1 = Client::factory()->create(['name' => 'Client One']);
        $client2 = Client::factory()->create(['name' => 'Client Two']);
        
        Meeting::factory()->count(3)->create(['client_id' => $client1->id]);
        Meeting::factory()->count(1)->create(['client_id' => $client2->id]);

        $browser->visit('/clients')
                ->assertSee('Client One')
                ->assertSee('Client Two')
                ->assertSee('3 meetings') // Should show meeting count for Client One
                ->assertSee('1 meeting')  // Should show meeting count for Client Two
                ->click("[data-testid=\"view-client-{$client1->id}\"]")
                ->assertPathIs("/clients/{$client1->id}")
                ->assertSee('3 meetings') // Should show meetings for this client
                ->assertSee('Client One');
    });

it('can search and filter clients')
    ->browse(function ($browser) {
        Client::factory()->create(['name' => 'Alpha Company', 'company' => 'Alpha Corp']);
        Client::factory()->create(['name' => 'Beta Company', 'company' => 'Beta Corp']);
        Client::factory()->create(['name' => 'Gamma Company', 'company' => 'Gamma Corp']);

        $browser->visit('/clients')
                ->assertSee('Alpha Company')
                ->assertSee('Beta Company')
                ->assertSee('Gamma Company')
                ->type('[data-testid="client-search"]', 'Alpha')
                ->click('[data-testid="search-button"]')
                ->assertSee('Alpha Company')
                ->assertDontSee('Beta Company')
                ->assertDontSee('Gamma Company')
                ->clear('[data-testid="client-search"]')
                ->click('[data-testid="clear-search-button"]')
                ->assertSee('Alpha Company')
                ->assertSee('Beta Company')
                ->assertSee('Gamma Company');
    });

it('can validate client form fields and handle errors', function () {
    // Test validation errors
    $response = $this->post(route('clients.store'), []);
    $response->assertSessionHasErrors(['name']);

    // Test unique email validation
    Client::factory()->create(['email' => 'existing@example.com']);
    
    $response = $this->post(route('clients.store'), [
        'name' => 'Test Client',
        'email' => 'existing@example.com'
    ]);
    $response->assertSessionHasErrors(['email']);

    // Test invalid email format
    $response = $this->post(route('clients.store'), [
        'name' => 'Test Client',
        'email' => 'invalid-email'
    ]);
    $response->assertSessionHasErrors(['email']);
});

it('can search and filter clients by various criteria', function () {
    Client::factory()->create(['name' => 'Alpha Company', 'company' => 'Alpha Corp']);
    Client::factory()->create(['name' => 'Beta Company', 'company' => 'Beta Corp']);
    Client::factory()->create(['name' => 'Gamma Company', 'company' => 'Gamma Corp']);

    // Test search functionality (if implemented)
    $response = $this->get(route('clients.index', ['search' => 'Alpha']));
    $response->assertStatus(200);
    
    // Test that all clients are returned when no search
    $response = $this->get(route('clients.index'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Clients/Index')
             ->has('clients', 3)
    );
});

it('can display client meeting counts and relationships', function () {
    $client1 = Client::factory()->create(['name' => 'Client One']);
    $client2 = Client::factory()->create(['name' => 'Client Two']);
    
    Meeting::factory()->count(3)->create(['client_id' => $client1->id]);
    Meeting::factory()->count(1)->create(['client_id' => $client2->id]);

    $response = $this->get(route('clients.index'));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Clients/Index')
             ->has('clients', 2)
    );

    // Test individual client view shows meetings
    $response = $this->get(route('clients.show', $client1));
    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Clients/Show')
             ->where('client.name', 'Client One')
             ->has('meetings', 3)
    );
});