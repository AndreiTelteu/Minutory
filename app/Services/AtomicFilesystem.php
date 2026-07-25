<?php

namespace App\Services;

use Illuminate\Support\Facades\File;
use RuntimeException;

class AtomicFilesystem
{
    public function beginReplacement(string $stagedPath, string $destinationPath): AtomicFileReplacement
    {
        $this->ensureDirectory(dirname($destinationPath));

        $backupPath = null;
        if ($this->exists($destinationPath)) {
            $backupPath = $destinationPath.'.backup.'.bin2hex(random_bytes(8));
            if (! $this->move($destinationPath, $backupPath)) {
                throw new RuntimeException('Unable to prepare the existing artifact for replacement.');
            }
        }

        $replacement = new AtomicFileReplacement(
            $this,
            $destinationPath,
            $backupPath,
        );

        if (! $this->move($stagedPath, $destinationPath)) {
            $replacement->rollback();

            throw new RuntimeException('Unable to store the replacement artifact.');
        }

        $replacement->markInstalled();

        return $replacement;
    }

    public function ensureDirectory(string $path): void
    {
        File::ensureDirectoryExists($path);
    }

    public function exists(string $path): bool
    {
        return File::exists($path);
    }

    public function move(string $from, string $to): bool
    {
        return @rename($from, $to);
    }

    public function delete(string $path): bool
    {
        return ! $this->exists($path) || File::delete($path);
    }
}
