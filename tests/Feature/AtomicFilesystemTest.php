<?php

use App\Services\AtomicFilesystem;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Storage;

class ControlledAtomicFilesystem extends AtomicFilesystem
{
    /** @var Closure(string, string): bool */
    public Closure $shouldFail;

    public function move(string $from, string $to): bool
    {
        if (($this->shouldFail)($from, $to)) {
            return false;
        }

        return parent::move($from, $to);
    }
}

it('leaves both source and destination intact when the initial backup rename fails', function () {
    Storage::fake('public');
    $destination = Storage::disk('public')->path('artifact.bin');
    $staged = Storage::disk('public')->path('staged.bin');
    File::put($destination, 'old');
    File::put($staged, 'new');

    $filesystem = new ControlledAtomicFilesystem;
    $filesystem->shouldFail = fn (string $from): bool => $from === $destination;

    expect(fn () => $filesystem->beginReplacement($staged, $destination))
        ->toThrow(RuntimeException::class, 'prepare');
    expect(File::get($destination))->toBe('old')
        ->and(File::get($staged))->toBe('new')
        ->and(glob($destination.'.backup.*'))->toBe([]);
});

it('restores the backup when installing the staged destination fails', function () {
    Storage::fake('public');
    $destination = Storage::disk('public')->path('artifact.bin');
    $staged = Storage::disk('public')->path('staged.bin');
    File::put($destination, 'old');
    File::put($staged, 'new');

    $filesystem = new ControlledAtomicFilesystem;
    $filesystem->shouldFail = fn (string $from): bool => $from === $staged;

    expect(fn () => $filesystem->beginReplacement($staged, $destination))
        ->toThrow(RuntimeException::class, 'replacement');
    expect(File::get($destination))->toBe('old')
        ->and(File::get($staged))->toBe('new')
        ->and(glob($destination.'.backup.*'))->toBe([]);
});
