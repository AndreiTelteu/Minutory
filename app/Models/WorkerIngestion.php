<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class WorkerIngestion extends Model
{
    protected $fillable = [
        'meeting_id',
        'worker_item_id',
        'start_transcript_server',
        'video_sha256',
        'video_bytes',
        'video_uploaded_at',
        'audio_sha256',
        'audio_bytes',
        'audio_uploaded_at',
        'transcript_sha256',
        'transcript_bytes',
        'transcript_uploaded_at',
        'server_transcription_dispatched_at',
    ];

    protected $casts = [
        'start_transcript_server' => 'boolean',
        'video_bytes' => 'integer',
        'video_uploaded_at' => 'datetime',
        'audio_bytes' => 'integer',
        'audio_uploaded_at' => 'datetime',
        'transcript_bytes' => 'integer',
        'transcript_uploaded_at' => 'datetime',
        'server_transcription_dispatched_at' => 'datetime',
    ];

    public function meeting(): BelongsTo
    {
        return $this->belongsTo(Meeting::class);
    }
}
