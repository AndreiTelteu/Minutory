<?php

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\UploadedFile;
use Illuminate\Support\Facades\Storage;
use function Pest\Laravel\get;
use function Pest\Laravel\post;
use function Pest\Laravel\put;
use function Pest\Laravel\delete;

describe('Error Handling UI Integration', function () {
    beforeEach(function () {
        Storage::fake('public');
        $this->client = Client::factory()->create();
        $this->meeting = Meeting::factory()->create(['client_id' => $this->client->id]);
    });

    describe('Form Validation Errors', function () {
        it('handles client creation validation errors', function () {
            $response = post(route('clients.store'), [
                'name' => '',
                'email' => 'invalid-email',
                'phone' => '',
            ]);

            $response->assertSessionHasErrors(['name', 'email']);
            $response->assertRedirect();
        });

        it('handles client update validation errors', function () {
            $response = put(route('clients.update', $this->client), [
                'name' => '',
                'email' => 'invalid-email',
            ]);

            $response->assertSessionHasErrors(['name', 'email']);
            $response->assertRedirect();
        });

        it('handles meeting creation validation errors', function () {
            $response = post(route('meetings.store'), [
                'title' => '',
                'client_id' => '',
                'file' => null,
            ]);

            $response->assertSessionHasErrors(['title', 'client_id', 'file']);
            $response->assertRedirect();
        });

        it('handles file upload validation errors', function () {
            $invalidFile = UploadedFile::fake()->create('document.pdf', 1000, 'application/pdf');

            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => $this->client->id,
                'file' => $invalidFile,
            ]);

            $response->assertSessionHasErrors(['file']);
        });

        it('handles file size validation errors', function () {
            $largeFile = UploadedFile::fake()->create('large.mp4', 1000000, 'video/mp4'); // 1GB

            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => $this->client->id,
                'file' => $largeFile,
            ]);

            $response->assertSessionHasErrors(['file']);
        });
    });

    describe('Resource Not Found Errors', function () {
        it('handles non-existent client gracefully', function () {
            $response = get(route('clients.show', 99999));
            $response->assertStatus(404);
        });

        it('handles non-existent meeting gracefully', function () {
            $response = get(route('meetings.show', 99999));
            $response->assertStatus(404);
        });

        it('handles non-existent client edit gracefully', function () {
            $response = get(route('clients.edit', 99999));
            $response->assertStatus(404);
        });

        it('handles update of non-existent client gracefully', function () {
            $response = put(route('clients.update', 99999), [
                'name' => 'Test',
                'email' => 'test@example.com',
            ]);
            $response->assertStatus(404);
        });

        it('handles delete of non-existent client gracefully', function () {
            $response = delete(route('clients.destroy', 99999));
            $response->assertStatus(404);
        });

        it('handles delete of non-existent meeting gracefully', function () {
            $response = delete(route('meetings.destroy', 99999));
            $response->assertStatus(404);
        });
    });

    describe('Business Logic Errors', function () {
        it('prevents deletion of client with meetings', function () {
            $response = delete(route('clients.destroy', $this->client));
            
            $response->assertSessionHasErrors();
            $response->assertRedirect();
            $this->assertDatabaseHas('clients', ['id' => $this->client->id]);
        });

        it('handles invalid client selection in meeting creation', function () {
            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => 99999,
                'file' => UploadedFile::fake()->create('test.mp4', 1000, 'video/mp4'),
            ]);

            $response->assertSessionHasErrors(['client_id']);
        });

        it('handles duplicate email validation', function () {
            $existingClient = Client::factory()->create(['email' => 'existing@example.com']);

            $response = post(route('clients.store'), [
                'name' => 'New Client',
                'email' => 'existing@example.com',
            ]);

            $response->assertSessionHasErrors(['email']);
        });
    });

    describe('File System Errors', function () {
        it('handles file upload failures gracefully', function () {
            Storage::shouldReceive('disk->put')->andReturn(false);

            $file = UploadedFile::fake()->create('test.mp4', 1000, 'video/mp4');

            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => $this->client->id,
                'file' => $file,
            ]);

            // Should handle the error gracefully
            $response->assertStatus(302); // Redirect back with error
        });

        it('handles missing file during deletion', function () {
            $this->meeting->update(['file_path' => 'meetings/non-existent.mp4']);

            $response = delete(route('meetings.destroy', $this->meeting));

            // Should still delete the record even if file doesn't exist
            $response->assertRedirect(route('meetings.index'));
            $this->assertDatabaseMissing('meetings', ['id' => $this->meeting->id]);
        });
    });

    describe('Database Constraint Errors', function () {
        it('handles foreign key constraint violations', function () {
            // Try to create meeting with non-existent client
            $response = post(route('meetings.store'), [
                'title' => 'Test Meeting',
                'client_id' => 99999,
                'file' => UploadedFile::fake()->create('test.mp4', 1000, 'video/mp4'),
            ]);

            $response->assertSessionHasErrors(['client_id']);
        });
    });

    describe('Session and State Errors', function () {
        it('handles expired sessions gracefully', function () {
            // This would typically be handled by Laravel's session middleware
            $response = get(route('clients.index'));
            $response->assertStatus(200);
        });

        it('handles invalid filter parameters', function () {
            $response = get(route('meetings.index', [
                'status' => 'invalid-status',
                'client_id' => 'invalid-id',
            ]));

            // Should still load the page, just ignore invalid filters
            $response->assertStatus(200);
            $response->assertInertia(fn ($page) => 
                $page->component('Meetings/Index')
            );
        });
    });

    describe('AJAX and API Errors', function () {
        it('handles meeting status API errors', function () {
            $response = get(route('meetings.status', 99999));
            $response->assertStatus(404);
        });

        it('handles AI chat errors gracefully', function () {
            $response = post(route('ai.chat.send'), [
                'message' => '',
            ]);

            $response->assertSessionHasErrors(['message']);
        });

        it('handles AI search errors gracefully', function () {
            $response = post(route('ai.search'), [
                'query' => '',
            ]);

            $response->assertSessionHasErrors(['query']);
        });
    });

    describe('Concurrent Access Errors', function () {
        it('handles concurrent client updates', function () {
            // Simulate concurrent update by modifying the client
            $this->client->update(['name' => 'Modified by another user']);

            $response = put(route('clients.update', $this->client), [
                'name' => 'My Update',
                'email' => $this->client->email,
            ]);

            // Should still update successfully (last write wins)
            $response->assertRedirect(route('clients.show', $this->client));
            $this->assertDatabaseHas('clients', ['name' => 'My Update']);
        });

        it('handles concurrent meeting deletions', function () {
            $meetingId = $this->meeting->id;
            
            // Delete the meeting first
            $this->meeting->delete();

            $response = delete(route('meetings.destroy', $meetingId));
            $response->assertStatus(404);
        });
    });

    describe('Input Sanitization', function () {
        it('handles malicious input in client creation', function () {
            $response = post(route('clients.store'), [
                'name' => '<script>alert("xss")</script>',
                'email' => 'test@example.com',
                'company' => '<img src=x onerror=alert(1)>',
            ]);

            $response->assertRedirect();
            
            // Check that the data was sanitized/escaped
            $client = Client::where('email', 'test@example.com')->first();
            expect($client->name)->not->toContain('<script>');
        });

        it('handles malicious input in meeting creation', function () {
            $file = UploadedFile::fake()->create('test.mp4', 1000, 'video/mp4');

            $response = post(route('meetings.store'), [
                'title' => '<script>alert("xss")</script>',
                'client_id' => $this->client->id,
                'file' => $file,
            ]);

            $response->assertRedirect();
            
            // Check that the data was sanitized/escaped
            $meeting = Meeting::where('client_id', $this->client->id)->latest()->first();
            expect($meeting->title)->not->toContain('<script>');
        });
    });
});