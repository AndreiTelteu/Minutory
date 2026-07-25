<?php

use App\Exceptions\WorkerApiException;
use App\Services\VideoProbe;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;

it('rejects unreadable video content through the configured ffprobe executable', function () {
    Storage::fake('public');
    config()->set('services.worker.artifacts.video.ffprobe_path', '/bin/false');
    config()->set('services.worker.artifacts.video.ffprobe_timeout', 1);
    $path = Storage::disk('public')->path('corrupt.mp4');
    File::put($path, 'not a media container');

    expect(fn () => app(VideoProbe::class)->validate($path))
        ->toThrow(WorkerApiException::class, 'not a readable video');
});
