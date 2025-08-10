<?php

use App\Models\Client;

it('can display clients index page', function () {
    $client = Client::factory()->create([
        'name' => 'Test Client',
        'email' => 'test@example.com',
        'company' => 'Test Company'
    ]);

    $response = $this->get(route('clients.index'));

    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Clients/Index')
             ->has('clients', 1)
             ->where('clients.0.name', 'Test Client')
    );
});

it('can create a new client', function () {
    $clientData = [
        'name' => 'New Client',
        'email' => 'new@example.com',
        'company' => 'New Company',
        'phone' => '123-456-7890'
    ];

    $response = $this->post(route('clients.store'), $clientData);

    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('success', 'Client created successfully.');
    
    $this->assertDatabaseHas('clients', $clientData);
});

it('validates required fields when creating client', function () {
    $response = $this->post(route('clients.store'), []);

    $response->assertSessionHasErrors(['name']);
});

it('validates unique email when creating client', function () {
    Client::factory()->create(['email' => 'existing@example.com']);

    $response = $this->post(route('clients.store'), [
        'name' => 'Test Client',
        'email' => 'existing@example.com'
    ]);

    $response->assertSessionHasErrors(['email']);
});

it('can update an existing client', function () {
    $client = Client::factory()->create([
        'name' => 'Original Name',
        'email' => 'original@example.com'
    ]);

    $updateData = [
        'name' => 'Updated Name',
        'email' => 'updated@example.com',
        'company' => 'Updated Company',
        'phone' => '987-654-3210'
    ];

    $response = $this->put(route('clients.update', $client), $updateData);

    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('success', 'Client updated successfully.');
    
    $this->assertDatabaseHas('clients', array_merge(['id' => $client->id], $updateData));
});

it('can delete a client without meetings', function () {
    $client = Client::factory()->create();

    $response = $this->delete(route('clients.destroy', $client));

    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('success', 'Client deleted successfully.');
    
    $this->assertDatabaseMissing('clients', ['id' => $client->id]);
});

it('cannot delete a client with meetings', function () {
    $client = Client::factory()->create();
    $client->meetings()->create([
        'title' => 'Test Meeting',
        'video_path' => 'test/path.mp4',
        'status' => 'pending',
        'uploaded_at' => now()
    ]);

    $response = $this->delete(route('clients.destroy', $client));

    $response->assertRedirect(route('clients.index'));
    $response->assertSessionHas('error', 'Cannot delete client with existing meetings.');
    
    $this->assertDatabaseHas('clients', ['id' => $client->id]);
});

it('can show client details with meetings', function () {
    $client = Client::factory()->create([
        'name' => 'Test Client',
        'company' => 'Test Company'
    ]);

    $response = $this->get(route('clients.show', $client));

    $response->assertStatus(200);
    $response->assertInertia(fn ($page) => 
        $page->component('Clients/Show')
             ->where('client.name', 'Test Client')
             ->where('client.company', 'Test Company')
    );
});