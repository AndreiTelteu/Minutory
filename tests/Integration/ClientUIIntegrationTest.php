<?php

use App\Models\Client;
use App\Models\Meeting;

use function Pest\Laravel\delete;
use function Pest\Laravel\get;
use function Pest\Laravel\post;
use function Pest\Laravel\put;

describe('Client UI Integration', function () {
    beforeEach(function () {
        $this->client = Client::factory()->create([
            'name' => 'Test Client',
            'email' => 'test@example.com',
            'phone' => '123-456-7890',
            'company' => 'Test Company',
        ]);
    });

    describe('Client Index Page', function () {
        it('displays clients index page', function () {
            $response = get(route('clients.index'));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients')
            );
        });

        it('displays client data in index', function () {
            $response = get(route('clients.index'));

            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.data', 1)
                ->has('clients.data.0', fn ($client) => $client->where('name', 'Test Client')
                    ->where('email', 'test@example.com')
                    ->where('company', 'Test Company')
                )
            );
        });

        it('displays client with meeting count', function () {
            Meeting::factory()->count(3)->create(['client_id' => $this->client->id]);

            $response = get(route('clients.index'));

            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.data.0', fn ($client) => $client->where('meetings_count', 3)
                )
            );
        });

        it('handles pagination', function () {
            Client::factory()->count(20)->create();

            $response = get(route('clients.index'));

            $response->assertInertia(fn ($page) => $page->component('Clients/Index')
                ->has('clients.links')
                ->has('clients.meta')
            );
        });
    });

    describe('Client Show Page', function () {
        it('displays client show page', function () {
            $response = get(route('clients.show', $this->client));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('client')
                ->has('meetings')
            );
        });

        it('displays client details', function () {
            $response = get(route('clients.show', $this->client));

            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('client', fn ($client) => $client->where('name', 'Test Client')
                    ->where('email', 'test@example.com')
                    ->where('phone', '123-456-7890')
                    ->where('company', 'Test Company')
                )
            );
        });

        it('displays client meetings', function () {
            $meeting = Meeting::factory()->create([
                'client_id' => $this->client->id,
                'title' => 'Test Meeting',
            ]);

            $response = get(route('clients.show', $this->client));

            $response->assertInertia(fn ($page) => $page->component('Clients/Show')
                ->has('meetings.data', 1)
                ->has('meetings.data.0', fn ($meeting) => $meeting->where('title', 'Test Meeting')
                )
            );
        });
    });

    describe('Client Create Page', function () {
        it('displays client create page', function () {
            $response = get(route('clients.create'));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Create')
            );
        });

        it('creates new client successfully', function () {
            $clientData = [
                'name' => 'New Client',
                'email' => 'new@example.com',
                'phone' => '987-654-3210',
                'company' => 'New Company',
            ];

            $response = post(route('clients.store'), $clientData);

            $response->assertRedirect(route('clients.index'));
            $this->assertDatabaseHas('clients', $clientData);
        });

        it('validates required fields', function () {
            $response = post(route('clients.store'), []);

            $response->assertSessionHasErrors(['name', 'email']);
        });

        it('validates email format', function () {
            $response = post(route('clients.store'), [
                'name' => 'Test',
                'email' => 'invalid-email',
            ]);

            $response->assertSessionHasErrors(['email']);
        });
    });

    describe('Client Edit Page', function () {
        it('displays client edit page', function () {
            $response = get(route('clients.edit', $this->client));

            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => $page->component('Clients/Edit')
                ->has('client')
            );
        });

        it('displays client data in edit form', function () {
            $response = get(route('clients.edit', $this->client));

            $response->assertInertia(fn ($page) => $page->component('Clients/Edit')
                ->has('client', fn ($client) => $client->where('name', 'Test Client')
                    ->where('email', 'test@example.com')
                )
            );
        });

        it('updates client successfully', function () {
            $updateData = [
                'name' => 'Updated Client',
                'email' => 'updated@example.com',
                'phone' => '555-555-5555',
                'company' => 'Updated Company',
            ];

            $response = put(route('clients.update', $this->client), $updateData);

            $response->assertRedirect(route('clients.show', $this->client));
            $this->assertDatabaseHas('clients', $updateData);
        });
    });

    describe('Client Delete', function () {
        it('deletes client successfully', function () {
            $response = delete(route('clients.destroy', $this->client));

            $response->assertRedirect(route('clients.index'));
            $this->assertDatabaseMissing('clients', ['id' => $this->client->id]);
        });

        it('prevents deletion of client with meetings', function () {
            Meeting::factory()->create(['client_id' => $this->client->id]);

            $response = delete(route('clients.destroy', $this->client));

            $response->assertSessionHasErrors();
            $this->assertDatabaseHas('clients', ['id' => $this->client->id]);
        });
    });
});
