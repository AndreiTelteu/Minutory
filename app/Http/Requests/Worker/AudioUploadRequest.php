<?php

namespace App\Http\Requests\Worker;

class AudioUploadRequest extends ArtifactUploadRequest
{
    public function rules(): array
    {
        return $this->artifactRules(
            config('services.worker.artifacts.audio.mime_types', []),
            (int) config('services.worker.artifacts.audio.max_bytes'),
        );
    }
}
