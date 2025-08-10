<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Client extends Model
{
    use HasFactory;
    protected $fillable = [
        'name',
        'email',
        'company',
        'phone',
    ];

    protected $casts = [
        'email_verified_at' => 'datetime',
    ];

    public function meetings(): HasMany
    {
        return $this->hasMany(Meeting::class);
    }
}
