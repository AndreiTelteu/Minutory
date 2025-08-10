<?php

use App\Http\Controllers\AIAgentController;
use App\Http\Controllers\ClientController;
use App\Http\Controllers\MeetingController;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::get('/', function () {
    return Inertia::render('Welcome');
})->name('home');

Route::resource('clients', ClientController::class);
Route::resource('meetings', MeetingController::class);

// API endpoint for real-time meeting status updates
Route::get('meetings/{meeting}/status', [MeetingController::class, 'status'])->name('meetings.status');

// AI Agent routes
Route::get('ai/chat', [AIAgentController::class, 'index'])->name('ai.chat');
Route::post('ai/chat', [AIAgentController::class, 'chat'])->name('ai.chat.send');
Route::post('ai/search', [AIAgentController::class, 'search'])->name('ai.search');
