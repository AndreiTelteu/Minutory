<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class AuthenticateWorker
{
    public function handle(Request $request, Closure $next): Response
    {
        $configuredToken = config('services.worker.token');

        if (! is_string($configuredToken) || $configuredToken === '') {
            return $this->error(
                'worker_auth_unavailable',
                'Worker authentication is not configured.',
                Response::HTTP_SERVICE_UNAVAILABLE,
            );
        }

        $authorization = $request->header('Authorization', '');
        $providedToken = null;

        if (is_string($authorization)
            && preg_match('/^Bearer[ \t]+(.+)$/i', $authorization, $matches) === 1) {
            $providedToken = $matches[1];
        }

        if (! is_string($providedToken) || ! hash_equals($configuredToken, $providedToken)) {
            return $this->error(
                'unauthenticated',
                'A valid Bearer token is required.',
                Response::HTTP_UNAUTHORIZED,
            );
        }

        return $next($request);
    }

    private function error(string $code, string $message, int $status): JsonResponse
    {
        return response()->json([
            'error' => [
                'code' => $code,
                'message' => $message,
            ],
        ], $status);
    }
}
