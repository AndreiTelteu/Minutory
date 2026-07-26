<?php

namespace App\Http\Requests\Worker;

use Closure;
use DateTimeImmutable;

class CreateMeetingRequest extends WorkerFormRequest
{
    public function rules(): array
    {
        return [
            'worker_item_id' => ['required', 'uuid:4'],
            'client_id' => ['required', 'integer', 'exists:clients,id'],
            'title' => ['required', 'string', 'max:255'],
            'meeting_at' => [
                'nullable',
                'string',
                function (string $attribute, mixed $value, Closure $fail): void {
                    if (! is_string($value)
                        || preg_match('/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:Z|[+-]\\d{2}:\\d{2})$/', $value) !== 1) {
                        $fail('The meeting at field must be an offset-bearing ISO-8601 datetime.');

                        return;
                    }

                    $parts = date_parse($value);
                    if ($parts['error_count'] > 0 || $parts['warning_count'] > 0) {
                        $fail('The meeting at field must be a valid datetime.');

                        return;
                    }

                    new DateTimeImmutable($value);
                },
            ],
            'duration_seconds' => ['nullable', 'integer', 'min:0', 'max:2147483647'],
            'language' => ['sometimes', 'string', 'in:ro,en'],
            'start_transcript_server' => ['required', 'boolean'],
        ];
    }
}
