<?php

namespace App\Http\Controllers;

use App\Jobs\TranscribeMeetingJob;
use App\Models\Client;
use App\Models\Meeting;
use App\Models\Person;
use Carbon\CarbonImmutable;
use Closure;
use DateTimeImmutable;
use DateTimeZone;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Facades\Validator;
use Illuminate\Validation\Rules\File;
use Illuminate\Validation\ValidationException;
use Inertia\Inertia;
use Inertia\Response;

class MeetingController extends Controller
{
    public function index(Request $request): Response
    {
        $filters = $this->validateIndexFilters($request);
        $query = Meeting::query()->with('client');

        // Apply filters if provided
        if (isset($filters['client_id'])) {
            $query->where('client_id', $filters['client_id']);
        }

        if (isset($filters['status'])) {
            $query->where('status', $filters['status']);
        }

        $effectiveTime = 'COALESCE(meetings.meeting_at, meetings.uploaded_at)';
        $timeZone = new DateTimeZone($filters['timezone'] ?? 'UTC');

        if (isset($filters['date_from'])) {
            $dateFromUtc = CarbonImmutable::createFromFormat('!Y-m-d', $filters['date_from'], $timeZone)
                ->startOfDay()
                ->utc();
            $query->where(DB::raw($effectiveTime), '>=', $dateFromUtc->format('Y-m-d H:i:s'));
        }

        if (isset($filters['date_to'])) {
            $dateToUtc = CarbonImmutable::createFromFormat('!Y-m-d', $filters['date_to'], $timeZone)
                ->endOfDay()
                ->utc();
            $query->where(DB::raw($effectiveTime), '<=', $dateToUtc->format('Y-m-d H:i:s'));
        }

        // Sorting
        $allowedSorts = ['meeting_at', 'uploaded_at', 'title', 'status', 'duration', 'client'];
        $sort = in_array($filters['sort'] ?? null, $allowedSorts, true) ? $filters['sort'] : 'meeting_at';
        $direction = ($filters['direction'] ?? null) === 'asc' ? 'asc' : 'desc';

        if ($sort === 'client') {
            $query->select('meetings.*')
                ->leftJoin('clients', 'clients.id', '=', 'meetings.client_id')
                ->orderBy('clients.name', $direction)
                ->orderBy('meetings.id', 'desc');
        } elseif ($sort === 'meeting_at') {
            $query->orderByRaw("CASE WHEN {$effectiveTime} IS NULL THEN 1 ELSE 0 END ASC")
                ->orderByRaw("{$effectiveTime} {$direction}")
                ->orderBy('meetings.id', 'desc');
        } elseif ($sort === 'uploaded_at') {
            $query->orderByRaw('CASE WHEN meetings.uploaded_at IS NULL THEN 1 ELSE 0 END ASC')
                ->orderBy('meetings.uploaded_at', $direction)
                ->orderBy('meetings.id', 'desc');
        } else {
            $column = match ($sort) {
                'title' => 'meetings.title',
                'status' => 'meetings.status',
                'duration' => 'meetings.duration',
                default => 'meetings.title',
            };

            $query->orderBy($column, $direction)
                ->orderBy('meetings.id', 'desc');
        }

        $meetings = $query->paginate(15)->withQueryString();
        $clients = Client::orderBy('name')->get(['id', 'name']);

        return Inertia::render('Meetings/Index', [
            'meetings' => $meetings,
            'clients' => $clients,
            'filters' => [
                ...$filters,
                'timezone' => $filters['timezone'] ?? 'UTC',
                'sort' => $sort,
                'direction' => $direction,
            ],
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
            'language' => 'sometimes|string|in:ro,en',
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
                'language' => $validated['language'] ?? 'ro',
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

        } catch (ValidationException $e) {
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
            $meeting->load([
                'client.persons' => fn ($query) => $query->orderBy('name'),
                'transcriptions' => fn ($query) => $query->orderBy('start_time'),
            ]);

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

    public function createPerson(Request $request, Meeting $meeting): RedirectResponse|JsonResponse
    {
        $validated = $request->validate([
            'name' => ['required', 'string', 'max:255'],
            'email' => ['nullable', 'email', 'max:255'],
        ]);

        $person = Person::create([
            'client_id' => $meeting->client_id,
            'name' => trim($validated['name']),
            'email' => isset($validated['email']) ? trim($validated['email']) : null,
        ]);

        if ($request->expectsJson()) {
            return response()->json(['person' => $person], 201);
        }

        return back()->with('success', 'Person created successfully.');
    }

    public function updateSpeakers(Request $request, Meeting $meeting): RedirectResponse
    {
        abort_unless($meeting->isCompleted(), 422, 'Speakers can only be edited after a meeting is completed.');

        $validated = $request->validate([
            'assignments' => ['required', 'array'],
            'assignments.*.speaker' => ['nullable', 'string', 'max:255'],
            'assignments.*.person_id' => ['nullable', 'integer'],
        ]);

        $assignments = collect($validated['assignments'])
            ->mapWithKeys(fn (array $assignment) => [$this->speakerKey($assignment['speaker'] ?? null) => $assignment['person_id'] ?? null]);
        $personIds = $assignments->filter()->values();
        $people = Person::query()
            ->where('client_id', $meeting->client_id)
            ->whereIn('id', $personIds)
            ->get()
            ->keyBy('id');

        if ($people->count() !== $personIds->unique()->count()) {
            throw ValidationException::withMessages([
                'assignments' => 'Each selected person must belong to this meeting client.',
            ]);
        }

        DB::transaction(function () use ($meeting, $assignments, $people): void {
            $meeting->transcriptions()->lockForUpdate()->get()->each(function ($transcription) use ($assignments, $people): void {
                $key = $this->speakerKey($transcription->speaker);

                if (! $assignments->has($key)) {
                    return;
                }

                $personId = $assignments->get($key);

                if (! $personId) {
                    $transcription->update(['person_id' => null]);

                    return;
                }

                $person = $people->get($personId);
                $transcription->update([
                    'person_id' => $person->id,
                    'speaker' => $person->name,
                ]);
            });
        });

        return back()->with('success', 'Speaker identities updated successfully.');
    }

    private function speakerKey(?string $speaker): string
    {
        return $speaker === null || trim($speaker) === '' ? '__unknown__' : trim($speaker);
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

    /**
     * @return array<string, mixed>
     */
    private function validateIndexFilters(Request $request): array
    {
        $validDate = function (string $attribute, mixed $value, Closure $fail): void {
            if (! is_string($value)
                || preg_match('/^\\d{4}-\\d{2}-\\d{2}$/', $value) !== 1
                || ! checkdate((int) substr($value, 5, 2), (int) substr($value, 8, 2), (int) substr($value, 0, 4))) {
                $fail("The {$attribute} field must be a real date in Y-m-d format.");
            }
        };

        $validTimeZone = function (string $attribute, mixed $value, Closure $fail): void {
            if (! is_string($value)
                || ! in_array($value, DateTimeZone::listIdentifiers(DateTimeZone::ALL_WITH_BC), true)) {
                $fail('The timezone field must be a valid IANA timezone identifier.');
            }
        };

        $validator = Validator::make($request->query(), [
            'client_id' => ['nullable', 'integer', 'exists:clients,id'],
            'status' => ['nullable', 'string', 'in:pending,processing,completed,failed'],
            'date_from' => ['nullable', 'string', $validDate],
            'date_to' => ['nullable', 'string', $validDate],
            'timezone' => ['nullable', 'string', $validTimeZone],
            'sort' => ['nullable', 'string', 'in:meeting_at,uploaded_at,title,status,duration,client'],
            'direction' => ['nullable', 'string', 'in:asc,desc'],
        ]);

        $validator->after(function ($validator) use ($request): void {
            $dateFrom = $request->query('date_from');
            $dateTo = $request->query('date_to');

            if (is_string($dateFrom)
                && is_string($dateTo)
                && preg_match('/^\\d{4}-\\d{2}-\\d{2}$/', $dateFrom) === 1
                && preg_match('/^\\d{4}-\\d{2}-\\d{2}$/', $dateTo) === 1
                && strcmp($dateTo, $dateFrom) < 0) {
                $validator->errors()->add('date_to', 'The date to field must be on or after date from.');
            }
        });

        if ($validator->fails()) {
            throw (new ValidationException($validator))->redirectTo(route('meetings.index'));
        }

        return $validator->validated();
    }
}
