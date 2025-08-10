<?php

namespace App\Http\Controllers;

use App\Models\Client;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;
use Illuminate\Http\RedirectResponse;
use Illuminate\Validation\Rule;

class ClientController extends Controller
{
    public function index(): Response
    {
        $clients = Client::withCount('meetings')
            ->orderBy('name')
            ->get();

        return Inertia::render('Clients/Index', [
            'clients' => $clients
        ]);
    }

    public function create(): Response
    {
        return Inertia::render('Clients/Create');
    }

    public function store(Request $request): RedirectResponse
    {
        $validated = $request->validate([
            'name' => 'required|string|max:255',
            'email' => 'nullable|email|unique:clients,email',
            'company' => 'nullable|string|max:255',
            'phone' => 'nullable|string|max:255',
        ]);

        Client::create($validated);

        return redirect()->route('clients.index')
            ->with('success', 'Client created successfully.');
    }

    public function show(Client $client): Response
    {
        $client->load(['meetings' => function ($query) {
            $query->orderBy('created_at', 'desc');
        }]);

        return Inertia::render('Clients/Show', [
            'client' => $client
        ]);
    }

    public function edit(Client $client): Response
    {
        return Inertia::render('Clients/Edit', [
            'client' => $client
        ]);
    }

    public function update(Request $request, Client $client): RedirectResponse
    {
        $validated = $request->validate([
            'name' => 'required|string|max:255',
            'email' => [
                'nullable',
                'email',
                Rule::unique('clients', 'email')->ignore($client->id)
            ],
            'company' => 'nullable|string|max:255',
            'phone' => 'nullable|string|max:255',
        ]);

        $client->update($validated);

        return redirect()->route('clients.index')
            ->with('success', 'Client updated successfully.');
    }

    public function destroy(Client $client): RedirectResponse
    {
        // Check if client has meetings
        if ($client->meetings()->count() > 0) {
            return redirect()->route('clients.index')
                ->with('error', 'Cannot delete client with existing meetings.');
        }

        $client->delete();

        return redirect()->route('clients.index')
            ->with('success', 'Client deleted successfully.');
    }
}