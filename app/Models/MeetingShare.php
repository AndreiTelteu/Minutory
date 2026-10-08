<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class MeetingShare extends Model
{
    protected $fillable = ['token', 'expires_at'];

    protected $casts = [
        'visits' => 'integer',
        'expires_at' => 'datetime',
    ];

    public function meeting(): BelongsTo
    {
        return $this->belongsTo(Meeting::class);
    }
}
