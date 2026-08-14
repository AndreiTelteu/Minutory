<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('worker_ingestions', function (Blueprint $table) {
            $table->char('speakers_sha256', 64)->nullable()->after('transcript_uploaded_at');
            $table->unsignedBigInteger('speakers_bytes')->nullable()->after('speakers_sha256');
            $table->timestamp('speakers_uploaded_at')->nullable()->after('speakers_bytes');
        });
    }

    public function down(): void
    {
        Schema::table('worker_ingestions', function (Blueprint $table) {
            $table->dropColumn(['speakers_sha256', 'speakers_bytes', 'speakers_uploaded_at']);
        });
    }
};
