<?php

namespace App\Http\Requests\Worker;

abstract class ArtifactUploadRequest extends WorkerFormRequest
{
    protected function prepareForValidation(): void
    {
        if ($this->has('replace')) {
            $this->merge([
                'replace' => filter_var($this->input('replace'), FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE),
            ]);
        }
    }

    protected function artifactRules(array $mimeTypes, int $maximumBytes): array
    {
        return [
            'file' => [
                'required',
                'file',
                'max:'.max(1, (int) ceil($maximumBytes / 1024)),
                'mimetypes:'.implode(',', $mimeTypes),
            ],
            'replace' => ['sometimes', 'boolean'],
        ];
    }
}
