<?php

namespace App\Http\Requests\Worker;

class VideoUploadRequest extends ArtifactUploadRequest
{
    public function rules(): array
    {
        return $this->artifactRules(
            config('services.worker.artifacts.video.mime_types', []),
            (int) config('services.worker.artifacts.video.max_bytes'),
        );
    }
}
