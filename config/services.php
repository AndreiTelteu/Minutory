<?php

return [

    /*
    |--------------------------------------------------------------------------
    | Third Party Services
    |--------------------------------------------------------------------------
    |
    | This file is for storing the credentials for third party services such
    | as Mailgun, Postmark, AWS and more. This file provides the de facto
    | location for this type of information, allowing packages to have
    | a conventional file to locate the various service credentials.
    |
    */

    'postmark' => [
        'token' => env('POSTMARK_TOKEN'),
    ],

    'ses' => [
        'key' => env('AWS_ACCESS_KEY_ID'),
        'secret' => env('AWS_SECRET_ACCESS_KEY'),
        'region' => env('AWS_DEFAULT_REGION', 'us-east-1'),
    ],

    'resend' => [
        'key' => env('RESEND_KEY'),
    ],

    'slack' => [
        'notifications' => [
            'bot_user_oauth_token' => env('SLACK_BOT_USER_OAUTH_TOKEN'),
            'channel' => env('SLACK_BOT_USER_DEFAULT_CHANNEL'),
        ],
    ],

    'ffmpeg' => [
        'image' => env('FFMPEG_DOCKER_IMAGE', 'jrottenberg/ffmpeg:latest'),
    ],
    'scriberr' => [
        'image' => env('SCRIBERR_DOCKER_IMAGE', 'scriberr-local:latest'),
    ],

    'transcribing' => [
        'driver' => env('TRANSCRIBING_DRIVER', 'parakeet'),
        'model_path' => env('TRANSCRIBING_MODEL_PATH', storage_path('app/model')),
        'language' => env('TRANSCRIBING_LANGUAGE', 'ro'),
        'device' => env('TRANSCRIBING_DEVICE', 'cpu'),
        'compute_type' => env('TRANSCRIBING_COMPUTE_TYPE', 'auto'),
    ],

    'worker' => [
        'token' => env('WORKER_API_TOKEN'),
        'auth_attempts_per_minute' => (int) env('WORKER_API_AUTH_ATTEMPTS_PER_MINUTE', 20),
        'auth_attempts_per_credential_per_minute' => (int) env('WORKER_API_AUTH_ATTEMPTS_PER_CREDENTIAL_PER_MINUTE', 10),
        'throttle_per_minute' => (int) env('WORKER_API_THROTTLE_PER_MINUTE', 60),
        'artifacts' => [
            'video' => [
                'max_bytes' => (int) env('WORKER_VIDEO_MAX_BYTES', 5_368_709_120),
                'ffprobe_path' => env('WORKER_FFPROBE_PATH', 'ffprobe'),
                'ffprobe_timeout' => (int) env('WORKER_FFPROBE_TIMEOUT', 15),
                'mime_types' => [
                    'video/mp4',
                    'video/quicktime',
                    'video/x-msvideo',
                    'video/webm',
                ],
                'extensions' => [
                    'video/mp4' => 'mp4',
                    'video/quicktime' => 'mov',
                    'video/x-msvideo' => 'avi',
                    'video/webm' => 'webm',
                ],
            ],
            'audio' => [
                'max_bytes' => (int) env('WORKER_AUDIO_MAX_BYTES', 1_073_741_824),
                'mime_types' => [
                    'audio/wav',
                    'audio/x-wav',
                    'audio/wave',
                    'audio/vnd.wave',
                ],
            ],
            'transcript' => [
                'max_bytes' => (int) env('WORKER_TRANSCRIPT_MAX_BYTES', 52_428_800),
                'mime_types' => [
                    'application/json',
                    'text/json',
                    'text/plain',
                ],
                'max_segments' => (int) env('WORKER_TRANSCRIPT_MAX_SEGMENTS', 100_000),
                'max_text_length' => (int) env('WORKER_TRANSCRIPT_MAX_TEXT_LENGTH', 10_000),
                'max_speaker_length' => (int) env('WORKER_TRANSCRIPT_MAX_SPEAKER_LENGTH', 255),
            ],
        ],
    ],

];
