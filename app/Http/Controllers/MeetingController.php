<?php

namespace App\Http\Controllers;

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use Carbon\CarbonImmutable;
use Closure;
use DateTimeImmutable;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Validation\Rules\File;
use Inertia\Inertia;
use Inertia\Response;

class MeetingController extends Controller
{
    public function index(Request $request): Response
    {
        $query = Meeting::query()->with('client');

        // Apply filters if provided
        if ($request->filled('client_id')) {
            $query->where('client_id', $request->client_id);
        }

        if ($request->filled('status')) {
            $query->where('status', $request->status);
        }

        if ($request->filled('date_from')) {
            $query->whereDate(DB::raw('COALESCE(meetings.meeting_at, meetings.uploaded_at)'), '>=', $request->date_from);
        }

        if ($request->filled('date_to')) {
            $query->whereDate(DB::raw('COALESCE(meetings.meeting_at, meetings.uploaded_at)'), '<=', $request->date_to);
        }

        // Sorting
        $allowedSorts = ['meeting_at', 'uploaded_at', 'title', 'status', 'duration', 'client'];
        $sort = in_array($request->get('sort'), $allowedSorts, true) ? $request->get('sort') : 'meeting_at';
        $direction = $request->get('direction') === 'asc' ? 'asc' : 'desc';

        if ($sort === 'client') {
            $query->select('meetings.*')
                ->leftJoin('clients', 'clients.id', '=', 'meetings.client_id')
                ->orderBy('clients.name', $direction)
                ->orderBy('meetings.id', 'desc');
        } elseif ($sort === 'meeting_at') {
            $query->orderByRaw("COALESCE(meetings.meeting_at, meetings.uploaded_at) {$direction}")
                ->orderBy('meetings.id', 'desc');
        } else {
            $column = match ($sort) {
                'title' => 'meetings.title',
                'status' => 'meetings.status',
                'duration' => 'meetings.duration',
                'uploaded_at' => 'meetings.uploaded_at',
                default => 'meetings.uploaded_at',
            };

            $query->orderBy($column, $direction)
                ->orderBy('meetings.id', 'desc');
        }

        $meetings = $query->paginate(15)->withQueryString();
        $clients = Client::orderBy('name')->get(['id', 'name']);

        return Inertia::render('Meetings/Index', [
            'meetings' => $meetings,
            'clients' => $clients,
            'filters' => $request->only(['client_id', 'status', 'date_from', 'date_to', 'sort', 'direction']),
        ]);
    }

    public function create(): Response
    {
        $clients = Client::orderBy('name')->get(['id', 'name']);

        return Inertia::render('Meetings/Create', [
            'clients' => $clients,
        ]);
    }

    public function store(Request $request): RedirectResponse
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'client_id' => 'required|exists:clients,id',
            'meeting_at' => $this->meetingAtRules(),
            'video' => [
                'required',
                'file',
                File::types(['mp4', 'mov', 'avi', 'webm'])
                    ->max(500 * 1024) // 500MB max
                    ->min(1024), // 1MB min
            ],
        ], [
            'title.required' => 'Please enter a meeting title.',
            'title.max' => 'Meeting title cannot exceed 255 characters.',
            'client_id.required' => 'Please select a client for this meeting.',
            'client_id.exists' => 'The selected client is invalid.',
            'meeting_at' => 'Please enter a valid meeting date and time.',
            'video.required' => 'Please select a video file to upload.',
            'video.file' => 'The uploaded file is not valid.',
            'video.types' => 'The video must be a file of type: MP4, MOV, AVI, or WebM.',
            'video.max' => 'The video file size cannot exceed 500MB.',
            'video.min' => 'The video file must be at least 1MB.',
        ]);

        $meeting = null;

        try {
            // Validate file integrity
            $videoFile = $request->file('video');
            if (! $videoFile->isValid()) {
                throw new \RuntimeException('The uploaded file is corrupted or invalid.');
            }

            // Check available disk space (basic check)
            $requiredSpace = $videoFile->getSize() * 1.5; // Account for processing overhead
            $availableSpace = disk_free_space(storage_path('app/public'));
            if ($availableSpace !== false && $availableSpace < $requiredSpace) {
                throw new \RuntimeException('Insufficient storage space available.');
            }

            // Create meeting record first
            $meeting = Meeting::create([
                'title' => $validated['title'],
                'client_id' => $validated['client_id'],
                'status' => 'pending',
                'meeting_at' => $this->normalizeMeetingAt($validated['meeting_at'] ?? null),
                'uploaded_at' => now(),
                'video_path' => '', // Will be updated after file storage
            ]);

            // Store video file with organized structure
            $originalExtension = $videoFile->getClientOriginalExtension();
            $fileName = "video.{$originalExtension}";
            $storagePath = "meetings/{$validated['client_id']}/{$meeting->id}";

            // Store the file in public disk so it can be served
            $videoPath = $videoFile->storeAs($storagePath, $fileName, 'public');

            if (! $videoPath) {
                throw new \RuntimeException('Failed to store video file.');
            }

            // Verify file was actually stored
            if (! Storage::disk('public')->exists($videoPath)) {
                throw new \RuntimeException('Video file was not properly saved.');
            }

            // Update meeting with video path and estimate duration (for demo purposes)
            $estimatedDuration = rand(300, 3600); // Random duration between 5-60 minutes
            $estimatedProcessingTime = max(10, $estimatedDuration / 60); // 1 second per minute of video, minimum 10 seconds

            $meeting->update([
                'video_path' => $videoPath,
                'duration' => $estimatedDuration,
                'estimated_processing_time' => (int) $estimatedProcessingTime,
            ]);

            // Dispatching may execute synchronously in local/test environments.
            // A processing failure must never roll back an already-uploaded meeting.
            try {
                TranscribeMeetingJob::dispatch($meeting);
            } catch (\Throwable $e) {
                \Log::error('Meeting transcription could not be started', [
                    'meeting_id' => $meeting->id,
                    'error' => $e->getMessage(),
                ]);

                $meeting->fresh()->update([
                    'status' => 'failed',
                    'processing_completed_at' => now(),
                    'error_message' => 'Meeting uploaded, but transcription could not be processed.',
                    'technical_error' => $e->getMessage(),
                ]);

                return redirect()->route('meetings.show', $meeting)
                    ->with('error', 'Meeting uploaded, but transcription could not be processed.');
            }

            return redirect()->route('meetings.show', $meeting)
                ->with('success', 'Meeting uploaded successfully and is being processed.');

        } catch (\Illuminate\Validation\ValidationException $e) {
            // Re-throw validation exceptions to be handled by Laravel
            throw $e;
        } catch (\RuntimeException $e) {
            // Clean up meeting record if created
            if ($meeting) {
                $meeting->delete();
            }

            return redirect()->back()
                ->withInput()
                ->with('error', $e->getMessage());
        } catch (\Exception $e) {
            // Clean up meeting record if created
            if ($meeting) {
                $meeting->delete();
            }

            // Log the error for debugging
            \Log::error('Meeting upload failed', [
                'error' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
                'user_input' => $request->only(['title', 'client_id', 'meeting_at']),
            ]);

            return redirect()->back()
                ->withInput()
                ->with('error', 'Failed to upload meeting video. Please try again or contact support if the problem persists.');
        }
    }

    public function show(Meeting $meeting): Response
    {
        try {
            $meeting->load(['client', 'transcriptions' => function ($query) {
                $query->orderBy('start_time');
            }]);

            // Generate video URL for frontend
            $videoUrl = null;
            $videoError = null;

            if ($meeting->video_path) {
                if (Storage::disk('public')->exists($meeting->video_path)) {
                    $videoUrl = asset('storage/'.$meeting->video_path);
                } else {
                    $videoError = 'Video file not found. It may have been moved or deleted.';
                    \Log::warning('Video file missing for meeting', [
                        'meeting_id' => $meeting->id,
                        'video_path' => $meeting->video_path,
                    ]);
                }
            } else {
                $videoError = 'No video file associated with this meeting.';
            }

            return Inertia::render('Meetings/Show', [
                'meeting' => $meeting,
                'videoUrl' => $videoUrl,
                'videoError' => $videoError,
            ]);
        } catch (\Exception $e) {
            \Log::error('Failed to load meeting', [
                'meeting_id' => $meeting->id,
                'error' => $e->getMessage(),
            ]);

            return redirect()->route('meetings.index')
                ->with('error', 'Failed to load meeting details. Please try again.');
        }
    }

    public function update(Request $request, Meeting $meeting): RedirectResponse
    {
        $validated = $request->validate([
            'title' => 'required|string|max:255',
            'client_id' => 'required|exists:clients,id',
            'meeting_at' => $this->meetingAtRules(),
        ]);

        $meeting->update([
            'title' => $validated['title'],
            'client_id' => $validated['client_id'],
            ...($request->exists('meeting_at')
                ? ['meeting_at' => $this->normalizeMeetingAt($validated['meeting_at'] ?? null)]
                : []),
        ]);

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

    /**
     * Get meeting status for real-time updates
     */
    public function status(Meeting $meeting)
    {
        try {
            return response()->json([
                'success' => true,
                'data' => [
                    'id' => $meeting->id,
                    'status' => $meeting->status,
                    'elapsed_time' => $meeting->elapsed_time,
                    'estimated_remaining_time' => $meeting->estimated_remaining_time,
                    'processing_progress' => $meeting->processing_progress,
                    'formatted_elapsed_time' => $meeting->formatted_elapsed_time,
                    'formatted_estimated_remaining_time' => $meeting->formatted_estimated_remaining_time,
                    'queue_progress' => $meeting->queue_progress,
                    'formatted_estimated_processing_time' => $meeting->formatted_estimated_processing_time,
                ],
            ]);
        } catch (\Exception $e) {
            \Log::error('Failed to get meeting status', [
                'meeting_id' => $meeting->id,
                'error' => $e->getMessage(),
            ]);

            return response()->json([
                'success' => false,
                'error' => 'Failed to retrieve meeting status',
            ], 500);
        }
    }

    /**
     * @return array<int, mixed>
     */
    private function meetingAtRules(): array
    {
        return [
            'nullable',
            'string',
            function (string $attribute, mixed $value, Closure $fail): void {
                if (! is_string($value)
                    || preg_match('/^[1-9]\\d{3}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}[+-](?:(?:0\\d|1[0-3]):[0-5]\\d|14:00)$/', $value) !== 1) {
                    $fail('The meeting date and time must include a UTC offset.');

                    return;
                }

                $parts = date_parse($value);
                if ($parts['error_count'] > 0 || $parts['warning_count'] > 0) {
                    $fail('The meeting date and time must be valid.');

                    return;
                }

                new DateTimeImmutable($value);
            },
        ];
    }

    private function normalizeMeetingAt(mixed $value): ?CarbonImmutable
    {
        return is_string($value) ? CarbonImmutable::parse($value)->utc() : null;
    }
}
