<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Meeting extends Model
{
    use HasFactory;
    protected $fillable = [
        'client_id',
        'title',
        'video_path',
        'status',
        'duration',
        'estimated_processing_time',
        'uploaded_at',
        'processing_started_at',
        'processing_completed_at',
        'error_message',
        'technical_error',
    ];

    protected $casts = [
        'uploaded_at' => 'datetime',
        'processing_started_at' => 'datetime',
        'processing_completed_at' => 'datetime',
        'duration' => 'integer',
        'estimated_processing_time' => 'integer',
    ];

    protected $appends = [
        'elapsed_time',
        'estimated_remaining_time',
        'processing_progress',
        'formatted_elapsed_time',
        'formatted_estimated_remaining_time',
        'queue_progress',
        'formatted_estimated_processing_time',
    ];

    public function client(): BelongsTo
    {
        return $this->belongsTo(Client::class);
    }

    public function transcriptions(): HasMany
    {
        return $this->hasMany(Transcription::class);
    }

    public function isProcessing(): bool
    {
        return $this->status === 'processing';
    }

    public function isCompleted(): bool
    {
        return $this->status === 'completed';
    }

    public function isFailed(): bool
    {
        return $this->status === 'failed';
    }

    /**
     * Get elapsed time since processing started (in seconds)
     */
    public function getElapsedTimeAttribute(): ?int
    {
        if (!$this->processing_started_at) {
            return null;
        }

        $endTime = $this->processing_completed_at ?? now();
        return $this->processing_started_at->diffInSeconds($endTime);
    }

    /**
     * Get estimated remaining time for processing (in seconds)
     */
    public function getEstimatedRemainingTimeAttribute(): ?int
    {
        if (!$this->isProcessing() || !$this->processing_started_at || !$this->duration) {
            return null;
        }

        // Estimate processing time as 1 second per minute of video (minimum 10 seconds)
        $estimatedTotalProcessingTime = max(10, $this->duration / 60);
        $elapsedTime = $this->elapsed_time;
        
        return max(0, (int) ($estimatedTotalProcessingTime - $elapsedTime));
    }

    /**
     * Get processing progress as percentage (0-100)
     */
    public function getProcessingProgressAttribute(): ?float
    {
        if (!$this->isProcessing() || !$this->processing_started_at || !$this->duration) {
            return null;
        }

        $estimatedTotalProcessingTime = max(10, $this->duration / 60);
        $elapsedTime = $this->elapsed_time;
        
        return min(100, ($elapsedTime / $estimatedTotalProcessingTime) * 100);
    }

    /**
     * Get formatted elapsed time string
     */
    public function getFormattedElapsedTimeAttribute(): ?string
    {
        $elapsed = $this->elapsed_time;
        if ($elapsed === null) {
            return null;
        }

        $minutes = floor($elapsed / 60);
        $seconds = $elapsed % 60;
        
        return sprintf('%d:%02d', $minutes, $seconds);
    }

    /**
     * Get formatted estimated remaining time string
     */
    public function getFormattedEstimatedRemainingTimeAttribute(): ?string
    {
        $remaining = $this->estimated_remaining_time;
        if ($remaining === null) {
            return null;
        }

        $minutes = floor($remaining / 60);
        $seconds = $remaining % 60;
        
        return sprintf('%d:%02d', $minutes, $seconds);
    }

    /**
     * Get queue progress for pending meetings (0-100)
     * This simulates progress based on time since upload
     */
    public function getQueueProgressAttribute(): ?float
    {
        if ($this->status !== 'pending' || !$this->estimated_processing_time || !$this->uploaded_at) {
            return null;
        }

        // Simulate queue progress based on time since upload
        // Assume it takes 30 seconds to start processing after upload
        $queueWaitTime = 30;
        $elapsedSinceUpload = $this->uploaded_at->diffInSeconds(now());
        
        return min(100, ($elapsedSinceUpload / $queueWaitTime) * 100);
    }

    /**
     * Get formatted estimated processing time string
     */
    public function getFormattedEstimatedProcessingTimeAttribute(): ?string
    {
        if (!$this->estimated_processing_time) {
            return null;
        }

        $minutes = floor($this->estimated_processing_time / 60);
        $seconds = $this->estimated_processing_time % 60;
        
        return sprintf('%d:%02d', $minutes, $seconds);
    }
}
