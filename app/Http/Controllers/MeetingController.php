<?php

namespace App\Http\Controllers;

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\Request;
use Illuminate\Http\RedirectResponse;
use Illuminate\Support\Facades\Storage;
use Illuminate\Validation\Rules\File;
use Inertia\Inertia;
use Inertia\Response;

class MeetingController extends Controller
{
    public function index(Request $request): Response
    {
        $query = Meeting::with('client')
            ->orderBy('created_at', 'desc');

        // Apply filters if provided
        if ($request->filled('client_id')) {
            $query->where('client_id', $request->client_id);
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        if ($request->filled('date_from')) {
            $query->whereDate('uploaded_at', '>=', $request->date_from);
        }

        if ($request->filled('date_to')) {
            $query->whereDate('uploaded_at', '<=', $request->date_to);
        }

        $meetings = $query->paginate(15);
        $clients = Client::orderBy('name')->get(['id', 'name']);

        return Inertia::render('Meetings/Index', [
            'meetings' => $meetings,
            'clients' => $clients,
            'filters' => $request->only(['client_id', 'status', 'date_from', 'date_to'])
        ]);
    }

    public function create(): Response
    {
        $clients = Client::orderBy('name')->get(['id', 'name']);

        return Inertia::render('Meetings/Create', [
            'clients' => $clients
        ]);
    }

    public function store(Request $request): RedirectResponse
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'client_id' => 'required|exists:clients,id',
            'video' => [
                'required',
                File::types(['mp4', 'mov', 'avi', 'webm'])
                    ->max(500 * 1024) // 500MB max
                    ->min(1024) // 1MB min
            ]
        ], [
            'video.types' => 'The video must be a file of type: MP4, MOV, AVI, or WebM.',
            'video.max' => 'The video file size cannot exceed 500MB.',
            'video.min' => 'The video file must be at least 1MB.',
            'client_id.required' => 'Please select a client for this meeting.',
            'client_id.exists' => 'The selected client is invalid.'
        ]);

        try {
            // Create meeting record first
            $meeting = Meeting::create([
                'title' => $validated['title'],
                'client_id' => $validated['client_id'],
                'status' => 'pending',
                'uploaded_at' => now(),
                'video_path' => '', // Will be updated after file storage
            ]);

            // Store video file with organized structure
            $videoFile = $request->file('video');
            $originalExtension = $videoFile->getClientOriginalExtension();
            $fileName = "video.{$originalExtension}";
            $storagePath = "meetings/{$validated['client_id']}/{$meeting->id}";
            
            // Store the file in public disk so it can be served
            $videoPath = $videoFile->storeAs($storagePath, $fileName, 'public');
            
            // Update meeting with video path
            $meeting->update(['video_path' => $videoPath]);

            return redirect()->route('meetings.index')
                ->with('success', 'Meeting uploaded successfully and is being processed.');

        } catch (\Exception $e) {
            // Clean up meeting record if file storage failed
            if (isset($meeting)) {
                $meeting->delete();
            }

            return redirect()->back()
                ->withInput()
                ->with('error', 'Failed to upload meeting video. Please try again.');
        }
    }

    public function show(Meeting $meeting): Response
    {
        $meeting->load(['client', 'transcriptions' => function ($query) {
            $query->orderBy('start_time');
        }]);

        // Generate video URL for frontend
        $videoUrl = null;
        if ($meeting->video_path && Storage::disk('public')->exists($meeting->video_path)) {
            $videoUrl = Storage::disk('public')->url($meeting->video_path);
        }

        return Inertia::render('Meetings/Show', [
            'meeting' => $meeting,
            'videoUrl' => $videoUrl
        ]);
    }

    public function update(Request $request, Meeting $meeting): RedirectResponse
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'client_id' => 'required|exists:clients,id',
        ]);

        $meeting->update($validated);

        return redirect()->route('meetings.show', $meeting)
            ->with('success', 'Meeting updated successfully.');
    }

    public function destroy(Meeting $meeting): RedirectResponse
    {
        try {
            // Delete video file if it exists
            if ($meeting->video_path && Storage::disk('public')->exists($meeting->video_path)) {
                Storage::disk('public')->delete($meeting->video_path);
                
                // Also try to delete the directory if it's empty
                $directory = dirname($meeting->video_path);
                $files = Storage::disk('public')->files($directory);
                if (empty($files)) {
                    Storage::disk('public')->deleteDirectory($directory);
                }
            }

            $meeting->delete();

            return redirect()->route('meetings.index')
                ->with('success', 'Meeting deleted successfully.');

        } catch (\Exception $e) {
            return redirect()->route('meetings.index')
                ->with('error', 'Failed to delete meeting. Please try again.');
        }
    }
}