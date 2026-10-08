<?php

namespace App\Http\Controllers;

use App\Models\Meeting;
use App\Models\MeetingShare;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\BinaryFileResponse;

class MeetingShareController extends Controller
{
    public function store(Meeting $meeting): JsonResponse
    {
        $share = $meeting->shares()->create(['token' => Str::random(64)]);

        return response()->json(['url' => route('share.show', $share->token)], 201);
    }

    public function show(MeetingShare $share): Response
    {
        $meeting = $share->meeting()->with([
            'client:id,name',
            'transcriptions' => fn ($query) => $query->orderBy('start_time'),
        ])->firstOrFail();

        $share->increment('visits');

        return Inertia::render('Meetings/Show', [
            'publicShare' => true,
            'meeting' => [
                ...$meeting->only([
                    'id', 'title', 'status', 'duration', 'language', 'meeting_at', 'uploaded_at',
                    'formatted_estimated_processing_time', 'formatted_elapsed_time',
                    'formatted_estimated_remaining_time',
                ]),
                'client' => ['name' => $meeting->client->name],
                'transcriptions' => $meeting->transcriptions->map(fn ($segment) => $segment->only([
                    'id', 'speaker', 'text', 'start_time', 'end_time', 'confidence',
                ])),
            ],
            'videoUrl' => $meeting->video_path && Storage::disk('public')->exists($meeting->video_path)
                ? route('share.video', $share->token)
                : null,
            'statusUrl' => route('share.status', $share->token),
        ]);
    }

    public function status(MeetingShare $share): JsonResponse
    {
        return response()->json(['data' => ['status' => $share->meeting->status]]);
    }

    public function video(MeetingShare $share): BinaryFileResponse
    {
        $path = $share->meeting->video_path;
        abort_unless($path && Storage::disk('public')->exists($path), 404);

        return response()->file(Storage::disk('public')->path($path));
    }
}
