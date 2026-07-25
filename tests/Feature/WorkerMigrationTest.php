<?php

use App\Models\Meeting;
use Illuminate\Support\Facades\Schema;

it('refuses rollback while metadata-only meetings still have null video paths', function () {
    Meeting::factory()->create(['video_path' => null]);

    $migration = require database_path('migrations/2026_07_25_000001_add_worker_fields_to_meetings_table.php');

    expect(fn () => $migration->down())
        ->toThrow(RuntimeException::class, 'metadata-only meetings');
    expect(Schema::hasColumn('meetings', 'meeting_at'))->toBeTrue()
        ->and(Meeting::query()->whereNull('video_path')->count())->toBe(1);
});
