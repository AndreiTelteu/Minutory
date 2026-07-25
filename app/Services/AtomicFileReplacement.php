<?php

namespace App\Services;

use Illuminate\Support\Facades\Log;
use Throwable;

class AtomicFileReplacement
{
    private bool $installed = false;

    public function __construct(
        private readonly AtomicFilesystem $filesystem,
        private readonly string $destinationPath,
        private ?string $backupPath,
    ) {}

    public function markInstalled(): void
    {
        $this->installed = true;
    }

    public function commit(): void
    {
        if ($this->backupPath === null) {
            return;
        }

        try {
            if ($this->filesystem->delete($this->backupPath)) {
                $this->backupPath = null;

                return;
            }
        } catch (Throwable $exception) {
            Log::warning('Committed artifact backup cleanup raised an exception.', [
                'backup_path' => $this->backupPath,
                'error' => $exception->getMessage(),
            ]);
        }

        Log::warning('Committed artifact replacement left a backup requiring cleanup.', [
            'backup_path' => $this->backupPath,
        ]);
    }

    public function rollback(): bool
    {
        try {
            $destinationExists = $this->filesystem->exists($this->destinationPath);
        } catch (Throwable $exception) {
            $this->logCriticalRecoveryFailure('destination_check_failed', $exception);

            return false;
        }

        if ($this->installed && $destinationExists) {
            try {
                $deleted = $this->filesystem->delete($this->destinationPath);
            } catch (Throwable $exception) {
                $this->logCriticalRecoveryFailure('replacement_delete_failed', $exception);

                return false;
            }

            if (! $deleted) {
                $this->logCriticalRecoveryFailure('replacement_delete_failed');

                return false;
            }
        }

        if ($this->backupPath === null) {
            return true;
        }

        try {
            $restored = $this->filesystem->move($this->backupPath, $this->destinationPath);
        } catch (Throwable $exception) {
            $this->logCriticalRecoveryFailure('backup_restore_failed', $exception);

            return false;
        }

        if (! $restored) {
            $this->logCriticalRecoveryFailure('backup_restore_failed');

            return false;
        }

        $this->backupPath = null;

        return true;
    }

    public function backupPath(): ?string
    {
        return $this->backupPath;
    }

    private function logCriticalRecoveryFailure(string $reason, ?Throwable $exception = null): void
    {
        Log::critical('Artifact recovery requires manual intervention.', [
            'reason' => $reason,
            'backup_path' => $this->backupPath,
            'destination_path' => $this->destinationPath,
            'error' => $exception?->getMessage(),
        ]);
    }
}
