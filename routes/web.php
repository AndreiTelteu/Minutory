<?php

use App\Http\Controllers\AIAgentController;
use App\Http\Controllers\ClientController;
use App\Http\Controllers\MeetingController;
use App\Http\Controllers\SearchController;
use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::get('/', function () {
    // Dashboard data
    $recentMeetings = Meeting::with('client')
        ->orderBy('created_at', 'desc')
        ->limit(5)
        ->get();

    $stats = [
        'total_clients' => Client::count(),
        'total_meetings' => Meeting::count(),
        'completed_meetings' => Meeting::where('status', 'completed')->count(),
        'processing_meetings' => Meeting::where('status', 'processing')->count(),
        'pending_meetings' => Meeting::where('status', 'pending')->count(),
        'failed_meetings' => Meeting::where('status', 'failed')->count(),
    ];

    $topClients = Client::withCount('meetings')
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
Route::post('meetings/{meeting}/people', [MeetingController::class, 'createPerson'])->name('meetings.people.store');
Route::put('meetings/{meeting}/speakers', [MeetingController::class, 'updateSpeakers'])->name('meetings.speakers.update');

// Spotlight search
Route::get('search', [SearchController::class, 'index'])->name('search');

// AI Agent routes
Route::get('ai/chat', [AIAgentController::class, 'index'])->name('ai.chat');
Route::post('ai/chat', [AIAgentController::class, 'chat'])->name('ai.chat.send');
Route::post('ai/search', [AIAgentController::class, 'search'])->name('ai.search');
