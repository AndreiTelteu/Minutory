<?php

use App\Exceptions\WorkerApiException;
use App\Http\Middleware\AuthenticateWorker;
use App\Http\Middleware\HandleInertiaRequests;
use App\Http\Middleware\ThrottleAuthenticatedWorker;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Middleware\AddLinkHeadersForPreloadedAssets;
use Illuminate\Http\Request;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware) {
        $middleware->trustProxies(at: '*');
        $middleware->alias([
            'worker.token' => AuthenticateWorker::class,
            'worker.throttle' => ThrottleAuthenticatedWorker::class,
        ]);

        $middleware->web(append: [
            HandleInertiaRequests::class,
            AddLinkHeadersForPreloadedAssets::class,
        ]);
    })
    ->withExceptions(function (Exceptions $exceptions) {
        $exceptions->render(function (\Throwable $exception, Request $request) {
            if (! $request->is('api/v1/worker/*') && ! $request->is('api/v1/worker')) {
                return null;
            }

            if ($exception instanceof WorkerApiException) {
                $error = [
                    'code' => $exception->errorCode,
                    'message' => $exception->getMessage(),
                ];

                if ($exception->details !== []) {
                    $error['details'] = $exception->details;
                }

                return response()->json(['error' => $error], $exception->status);
            }

            $status = $exception instanceof HttpExceptionInterface
                ? $exception->getStatusCode()
                : 500;

            [$code, $message] = match ($status) {
                404 => ['not_found', 'The requested worker API resource was not found.'],
                405 => ['method_not_allowed', 'The request method is not allowed.'],
                413 => ['payload_too_large', 'The request body exceeds the server upload limit.'],
                429 => ['rate_limit_exceeded', 'Too many worker API requests.'],
                default => ['server_error', 'The worker API could not process the request.'],
            };

            return response()->json([
                'error' => [
                    'code' => $code,
                    'message' => $message,
                ],
            ], $status);
        });
    })->create();
