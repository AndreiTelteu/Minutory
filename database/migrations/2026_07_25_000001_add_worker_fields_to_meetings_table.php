<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('meetings', function (Blueprint $table) {
            $table->timestamp('meeting_at')->nullable()->index()->after('duration');
            $table->string('video_path', 500)->nullable()->change();
        });
    }

    public function down(): void
    {
        DB::table('meetings')->whereNull('video_path')->update(['video_path' => '']);

        Schema::table('meetings', function (Blueprint $table) {
            $table->dropIndex(['meeting_at']);
            $table->dropColumn('meeting_at');
            $table->string('video_path', 500)->nullable(false)->change();
        });
    }
};
