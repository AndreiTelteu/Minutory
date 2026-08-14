<?php

namespace App\Http\Requests\Worker;

class SpeakersUploadRequest extends ArtifactUploadRequest
{
    public function rules(): array
    {
        return $this->artifactRules(
            config('services.worker.artifacts.speakers.mime_types', []),
            (int) config('services.worker.artifacts.speakers.max_bytes'),
        );
    }
}
