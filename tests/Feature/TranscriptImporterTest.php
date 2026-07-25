<?php

use App\Models\Meeting;
use App\Models\Transcription;
use App\Services\AtomicFilesystem;
use App\Services\TranscriptImporter;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;

function normalizedTranscript(array $segments): string
{
    return json_encode([
        'driver' => 'worker',
        'model' => 'large-v3',
        'language' => 'ro',
        'language_probability' => 0.98,
        'duration' => 12.5,
        'runtime' => (object) [],
        'segments' => $segments,
    ], JSON_THROW_ON_ERROR);
}

class TranscriptRestoreFailingFilesystem extends AtomicFilesystem
{
    public function move(string $from, string $to): bool
    {
        if (str_contains($from, '.backup.') && ! str_contains($to, '.backup.')) {
            return false;
        }

        return parent::move($from, $to);
    }
}

it('validates, deterministically orders, and atomically imports normalized segments', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    $old = Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'old transcript',
    ]);
    $path = Storage::disk('public')->path('new-transcript.json');
    File::put($path, normalizedTranscript([
        ['speaker' => 'B', 'text' => ' second ', 'start' => 5, 'end' => 7, 'confidence' => 0.75],
        ['speaker' => 'A', 'text' => 'first', 'start' => 0, 'end' => 2],
    ]));

    $count = app(TranscriptImporter::class)->import($meeting, $path);

    expect($count)->toBe(2)
        ->and(Transcription::query()->find($old->id))->toBeNull()
        ->and($meeting->transcriptions()->orderBy('id')->pluck('text')->all())
        ->toBe(['first', 'second'])
        ->and($meeting->transcriptions()->orderBy('id')->first()->speaker)->toBe('A')
        ->and($meeting->transcriptions()->orderBy('id')->get()[1]->confidence)->toBe('0.75');
});

it('preserves existing rows when the replacement is invalid', function (string $json) {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    $old = Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'known good transcript',
    ]);
    $path = Storage::disk('public')->path('invalid-transcript.json');
    File::put($path, $json);

    expect(fn () => app(TranscriptImporter::class)->import($meeting, $path))
        ->toThrow(RuntimeException::class)
        ->and(Transcription::query()->find($old->id)?->text)
        ->toBe('known good transcript');
})->with([
    'invalid JSON' => ['{invalid'],
    'missing normalized fields' => [json_encode(['segments' => []])],
    'negative timestamp' => [normalizedTranscript([
        ['speaker' => 'A', 'text' => 'bad', 'start' => -1, 'end' => 2],
    ])],
    'empty text' => [normalizedTranscript([
        ['speaker' => 'A', 'text' => '  ', 'start' => 0, 'end' => 2],
    ])],
    'confidence out of bounds' => [normalizedTranscript([
        ['speaker' => 'A', 'text' => 'bad', 'start' => 0, 'end' => 2, 'confidence' => 1.1],
    ])],
    'timestamp overflow' => [normalizedTranscript([
        ['speaker' => 'A', 'text' => 'bad', 'start' => 0, 'end' => 10_000_000],
    ])],
]);

it('preserves the durable file and rows when a staged replacement is invalid', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'known good row',
    ]);
    $destination = Storage::disk('public')->path('transcript.json');
    $staged = Storage::disk('public')->path('staged.json');
    File::put($destination, normalizedTranscript([
        ['speaker' => 'A', 'text' => 'known good file', 'start' => 0, 'end' => 1],
    ]));
    $oldFile = File::get($destination);
    File::put($staged, '{broken');

    expect(fn () => app(TranscriptImporter::class)->replace($meeting, $staged, $destination))
        ->toThrow(RuntimeException::class)
        ->and(File::get($destination))->toBe($oldFile)
        ->and($meeting->transcriptions()->first()->text)->toBe('known good row');
});

it('accepts the maximum representable transcription timestamp', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    $path = Storage::disk('public')->path('boundary.json');
    File::put($path, normalizedTranscript([
        ['speaker' => 'A', 'text' => 'boundary', 'start' => 9_999_999.998, 'end' => 9_999_999.999],
    ]));

    app(TranscriptImporter::class)->import($meeting, $path);

    expect($meeting->transcriptions()->first()->end_time)->toBe('9999999.999');
});

it('restores the prior transcript and rows when a post-swap database callback fails', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'old row',
    ]);
    $destination = Storage::disk('public')->path('transcript.json');
    $staged = Storage::disk('public')->path('staged.json');
    File::put($destination, normalizedTranscript([
        ['speaker' => 'A', 'text' => 'old file', 'start' => 0, 'end' => 1],
    ]));
    $oldFile = File::get($destination);
    File::put($staged, normalizedTranscript([
        ['speaker' => 'B', 'text' => 'new file', 'start' => 1, 'end' => 2],
    ]));

    expect(fn () => app(TranscriptImporter::class)->replace(
        $meeting,
        $staged,
        $destination,
        fn () => throw new RuntimeException('injected callback failure'),
    ))->toThrow(RuntimeException::class, 'injected callback failure');

    expect(File::get($destination))->toBe($oldFile)
        ->and($meeting->transcriptions()->first()->text)->toBe('old row')
        ->and(glob($destination.'.backup.*'))->toBe([]);
});

it('retains and critically logs the transcript backup if restoration fails', function () {
    Storage::fake('public');
    Log::spy();
    $meeting = Meeting::factory()->create();
    Transcription::factory()->create([
        'meeting_id' => $meeting->id,
        'text' => 'old row',
    ]);
    $destination = Storage::disk('public')->path('transcript.json');
    $staged = Storage::disk('public')->path('staged.json');
    File::put($destination, normalizedTranscript([
        ['speaker' => 'A', 'text' => 'old file', 'start' => 0, 'end' => 1],
    ]));
    $oldFile = File::get($destination);
    File::put($staged, normalizedTranscript([
        ['speaker' => 'B', 'text' => 'new file', 'start' => 1, 'end' => 2],
    ]));
    $importer = new TranscriptImporter(new TranscriptRestoreFailingFilesystem);

    expect(fn () => $importer->replace(
        $meeting,
        $staged,
        $destination,
        fn () => throw new RuntimeException('injected callback failure'),
    ))->toThrow(RuntimeException::class);

    $backups = glob($destination.'.backup.*');
    expect($backups)->toHaveCount(1)
        ->and(File::get($backups[0]))->toBe($oldFile)
        ->and(File::exists($destination))->toBeFalse()
        ->and($meeting->transcriptions()->first()->text)->toBe('old row');

    Log::shouldHaveReceived('critical')
        ->once()
        ->withArgs(fn (string $message, array $context): bool => $message === 'Artifact recovery requires manual intervention.'
            && $context['backup_path'] === $backups[0]);
});

it('enforces configured transcript byte and segment limits', function () {
    Storage::fake('public');
    $meeting = Meeting::factory()->create();
    $path = Storage::disk('public')->path('limited.json');
    File::put($path, normalizedTranscript([
        ['speaker' => 'A', 'text' => 'one', 'start' => 0, 'end' => 1],
        ['speaker' => 'B', 'text' => 'two', 'start' => 1, 'end' => 2],
    ]));

    config()->set('services.worker.artifacts.transcript.max_segments', 1);
    expect(fn () => app(TranscriptImporter::class)->import($meeting, $path))
        ->toThrow(RuntimeException::class, 'too many segments');

    config()->set('services.worker.artifacts.transcript.max_segments', 100_000);
    config()->set('services.worker.artifacts.transcript.max_bytes', 10);
    expect(fn () => app(TranscriptImporter::class)->import($meeting, $path))
        ->toThrow(RuntimeException::class, 'maximum size');
});
