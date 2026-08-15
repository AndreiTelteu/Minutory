<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('transcriptions', function (Blueprint $table) {
            $table->string('detected_speaker')->nullable()->after('person_id');
        });

        DB::table('transcriptions')->update(['detected_speaker' => DB::raw('speaker')]);
    }

    public function down(): void
    {
        Schema::table('transcriptions', function (Blueprint $table) {
            $table->dropColumn('detected_speaker');
        });
    }
};
