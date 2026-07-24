<?php

namespace App\Http\Controllers;

use App\Models\Client;
use App\Models\Meeting;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class SearchController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        $query = trim((string) $request->query('q', ''));

        if (mb_strlen($query) < 1) {
            return response()->json(['clients' => [], 'meetings' => []]);
        }

        $escaped = addcslashes($query, '\\%_');
        $like = "%{$escaped}%";

        $clients = Client::query()
            ->where('name', 'like', $like)
            ->orWhere('company', 'like', $like)
            ->orderBy('name')
            ->limit(5)
            ->get(['id', 'name', 'company']);

        $meetings = Meeting::query()
            ->with('client:id,name')
            ->where('title', 'like', $like)
            ->orderBy('created_at', 'desc')
            ->limit(8)
            ->get(['id', 'title', 'status', 'client_id', 'created_at']);

        return response()->json([
            'clients' => $clients,
            'meetings' => $meetings,
        ]);
    }
}
