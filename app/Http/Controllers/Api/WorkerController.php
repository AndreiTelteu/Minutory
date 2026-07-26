<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Http\Requests\Worker\AudioUploadRequest;
use App\Http\Requests\Worker\CreateMeetingRequest;
use App\Http\Requests\Worker\TranscriptUploadRequest;
use App\Http\Requests\Worker\VideoUploadRequest;
use App\Models\Client;
use App\Models\Meeting;
use App\Models\WorkerIngestion;
use App\Services\WorkerArtifactService;
use App\Services\WorkerMeetingService;
use Illuminate\Http\JsonResponse;
use Illuminate\Support\Facades\Storage;

class WorkerController extends Controller
{
    public function clients(): JsonResponse
    {
        return response()->json([
            'data' => Client::query()
                ->orderBy('name')
                ->orderBy('id')
                ->get(['id', 'name']),
        ]);
    }

    public function storeMeeting(
        CreateMeetingRequest $request,
        WorkerMeetingService $service,
    ): JsonResponse {
        $result = $service->createOrReplay($request->validated());

        return response()->json([
            'data' => $this->meetingData($result['meeting']),
        ], $result['created'] ? 201 : 200);
    }

    public function showMeeting(Meeting $meeting): JsonResponse
    {
        $ingestion = $meeting->workerIngestion()->first();
        if ($ingestion === null) {
            abort(404);
        }

        $meeting->setRelation('workerIngestion', $ingestion);

        return response()->json([
            'data' => $this->meetingData($meeting, includeArtifacts: true),
        ]);
    }

    public function video(
        VideoUploadRequest $request,
        Meeting $meeting,
        WorkerArtifactService $service,
    ): JsonResponse {
        return $this->artifactResponse($service->storeVideo(
            $meeting,
            $request->file('file'),
            $request->boolean('replace'),
        ));
    }

    public function audio(
        AudioUploadRequest $request,
        Meeting $meeting,
        WorkerArtifactService $service,
    ): JsonResponse {
        return $this->artifactResponse($service->storeAudio(
            $meeting,
            $request->file('file'),
            $request->boolean('replace'),
        ));
    }

    public function transcript(
        TranscriptUploadRequest $request,
        Meeting $meeting,
        WorkerArtifactService $service,
    ): JsonResponse {
        return $this->artifactResponse($service->storeTranscript(
            $meeting,
            $request->file('file'),
            $request->boolean('replace'),
        ));
    }

    private function artifactResponse(array $artifact): JsonResponse
    {
        return response()->json(['data' => $artifact]);
    }

    private function meetingData(Meeting $meeting, bool $includeArtifacts = false): array
    {
        /** @var WorkerIngestion $ingestion */
        $ingestion = $meeting->workerIngestion;

        $data = [
            'id' => $meeting->id,
            'worker_item_id' => $ingestion->worker_item_id,
            'client_id' => $meeting->client_id,
            'title' => $meeting->title,
            'meeting_at' => $meeting->meeting_at?->utc()->toIso8601String(),
            'duration_seconds' => $meeting->duration,
            'language' => $meeting->language,
            'status' => $meeting->status,
            'start_transcript_server' => $ingestion->start_transcript_server,
            'server_transcription_dispatched_at' => $ingestion->server_transcription_dispatched_at?->toIso8601String(),
        ];

        if ($includeArtifacts) {
            $data['artifacts'] = [
                'video' => $this->artifactData(
                    $ingestion,
                    'video',
                    $meeting->video_path !== null && Storage::disk('public')->exists($meeting->video_path),
                ),
                'audio' => $this->artifactData(
                    $ingestion,
                    'audio',
                    Storage::disk('public')->exists($this->relativeArtifactPath($meeting, 'audio.wav')),
                ),
                'transcript' => $this->artifactData(
                    $ingestion,
                    'transcript',
                    Storage::disk('public')->exists($this->relativeArtifactPath($meeting, 'transcript.json')),
                ),
            ];
        }

        return $data;
    }

    private function artifactData(WorkerIngestion $ingestion, string $artifact, bool $fileExists): array
    {
        $hash = $ingestion->getAttribute("{$artifact}_sha256");
        $uploadedAt = $ingestion->getAttribute("{$artifact}_uploaded_at");

        return [
            'uploaded' => $hash !== null && $fileExists,
            'sha256' => $hash,
            'bytes' => $ingestion->getAttribute("{$artifact}_bytes"),
            'uploaded_at' => $uploadedAt?->toIso8601String(),
        ];
    }

    private function relativeArtifactPath(Meeting $meeting, string $filename): string
    {
        return "meetings/{$meeting->client_id}/{$meeting->id}/{$filename}";
    }
}
