<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Transcription extends Model
{
    use HasFactory;
    protected $fillable = [
        'meeting_id',
        'speaker',
        'text',
        'start_time',
        'end_time',
        'confidence',
    ];

    protected $casts = [
        'start_time' => 'decimal:3',
        'end_time' => 'decimal:3',
        'confidence' => 'decimal:2',
    ];

    public function meeting(): BelongsTo
    {
        return $this->belongsTo(Meeting::class);
    }

    public function getFormattedStartTimeAttribute(): string
    {
        $minutes = floor($this->start_time / 60);
        $seconds = $this->start_time % 60;
        return sprintf('%02d:%05.2f', $minutes, $seconds);
    }

    public function getFormattedEndTimeAttribute(): string
    {
        $minutes = floor($this->end_time / 60);
        $seconds = $this->end_time % 60;
        return sprintf('%02d:%05.2f', $minutes, $seconds);
    }

    public function getDurationAttribute(): float
    {
        return $this->end_time - $this->start_time;
    }
}
