<?php

use App\Http\Controllers\AIAgentController;
use App\Http\Controllers\ClientController;
use App\Http\Controllers\MeetingController;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::get('/', function () {
    // Dashboard data
    $recentMeetings = \App\Models\Meeting::with('client')
        ->orderBy('created_at', 'desc')
        ->limit(5)
        ->get();

    $stats = [
        'total_clients' => \App\Models\Client::count(),
        'total_meetings' => \App\Models\Meeting::count(),
        'completed_meetings' => \App\Models\Meeting::where('status', 'completed')->count(),
        'processing_meetings' => \App\Models\Meeting::where('status', 'processing')->count(),
        'pending_meetings' => \App\Models\Meeting::where('status', 'pending')->count(),
        'failed_meetings' => \App\Models\Meeting::where('status', 'failed')->count(),
    ];

    $topClients = \App\Models\Client::withCount('meetings')
        ->orderBy('meetings_count', 'desc')
        ->limit(5)
        ->get(['id', 'name']);

    return Inertia::render('Dashboard', [
        'recentMeetings' => $recentMeetings,
        'stats' => $stats,
        'topClients' => $topClients,
    ]);
})->name('home');

Route::resource('clients', ClientController::class);
Route::resource('meetings', MeetingController::class);

// API endpoint for real-time meeting status updates
Route::get('meetings/{meeting}/status', [MeetingController::class, 'status'])->name('meetings.status');

// AI Agent routes
Route::get('ai/chat', [AIAgentController::class, 'index'])->name('ai.chat');
Route::post('ai/chat', [AIAgentController::class, 'chat'])->name('ai.chat.send');
Route::post('ai/search', [AIAgentController::class, 'search'])->name('ai.search');
