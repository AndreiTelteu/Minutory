<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Symfony\Component\HttpFoundation\Response;

class ThrottleAuthenticatedWorker
{
    public function handle(Request $request, Closure $next): Response
    {
        $identity = (string) $request->attributes->get('worker_auth_identity', 'missing');
        $key = 'worker-api:'.$identity;
        $maximumAttempts = (int) config('services.worker.throttle_per_minute', 60);

        if (RateLimiter::tooManyAttempts($key, $maximumAttempts)) {
            return new JsonResponse([
                'error' => [
                    'code' => 'rate_limit_exceeded',
                    'message' => 'Too many worker API requests.',
                ],
            ], 429);
        }

        RateLimiter::hit($key, 60);

        return $next($request);
    }
}
