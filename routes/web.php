<?php

use App\Http\Controllers\ClientController;
use App\Http\Controllers\MeetingController;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;

Route::get('/', function () {
    return Inertia::render('Welcome');
})->name('home');

Route::resource('clients', ClientController::class);
Route::resource('meetings', MeetingController::class);
