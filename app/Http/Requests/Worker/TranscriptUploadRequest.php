<?php

namespace App\Http\Requests\Worker;

class TranscriptUploadRequest extends ArtifactUploadRequest
{
    public function rules(): array
    {
        return $this->artifactRules(
            config('services.worker.artifacts.transcript.mime_types', []),
            (int) config('services.worker.artifacts.transcript.max_bytes'),
        );
    }
}
