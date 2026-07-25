<?php

namespace App\Providers;

use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        RateLimiter::for('worker-auth-attempts', function (Request $request): array {
            $key = (string) config('app.key');
            $remoteAddress = (string) $request->server('REMOTE_ADDR', 'unknown');
            $authorization = (string) $request->header('Authorization', '');

            return [
                Limit::perMinute((int) config('services.worker.auth_attempts_per_minute', 20))
                    ->by('worker-auth-remote:'.hash_hmac('sha256', $remoteAddress, $key)),
                Limit::perMinute((int) config('services.worker.auth_attempts_per_credential_per_minute', 10))
                    ->by('worker-auth-credential:'.hash_hmac('sha256', $authorization, $key)),
            ];
        });
    }
}
