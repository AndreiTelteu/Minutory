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

];
