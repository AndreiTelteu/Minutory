<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('worker_ingestions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('meeting_id')->unique()->constrained()->cascadeOnDelete();
            $table->uuid('worker_item_id')->unique();
            $table->boolean('start_transcript_server')->default(false);

            foreach (['video', 'audio', 'transcript'] as $artifact) {
                $table->char("{$artifact}_sha256", 64)->nullable();
                $table->unsignedBigInteger("{$artifact}_bytes")->nullable();
                $table->timestamp("{$artifact}_uploaded_at")->nullable();
            }

            $table->timestamp('server_transcription_dispatched_at')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('worker_ingestions');
    }
};
