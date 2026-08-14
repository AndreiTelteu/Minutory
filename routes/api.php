<?php

use App\Http\Controllers\Api\WorkerController;
use Illuminate\Support\Facades\Route;

Route::prefix('v1/worker')
    ->middleware(['throttle:worker-auth-attempts', 'worker.token', 'worker.throttle'])
    ->group(function (): void {
        Route::get('clients', [WorkerController::class, 'clients']);
        Route::post('meetings', [WorkerController::class, 'storeMeeting']);
        Route::get('meetings/{meeting}', [WorkerController::class, 'showMeeting']);
        Route::post('meetings/{meeting}/artifacts/video', [WorkerController::class, 'video']);
        Route::post('meetings/{meeting}/artifacts/audio', [WorkerController::class, 'audio']);
        Route::post('meetings/{meeting}/artifacts/transcript', [WorkerController::class, 'transcript']);
        Route::post('meetings/{meeting}/artifacts/speakers', [WorkerController::class, 'speakers']);
    });
