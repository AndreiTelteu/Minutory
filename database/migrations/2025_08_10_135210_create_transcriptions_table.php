<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('transcriptions', function (Blueprint $table) {
            $table->id();
            $table->foreignId('meeting_id')->constrained()->onDelete('cascade');
            $table->string('speaker')->nullable();
            $table->text('text');
            $table->decimal('start_time', 10, 3); // seconds with millisecond precision
            $table->decimal('end_time', 10, 3);   // seconds with millisecond precision
            $table->decimal('confidence', 3, 2)->default(1.00); // 0.00 to 1.00
            $table->timestamps();

            // Indexes for performance and search
            $table->index('meeting_id');
            $table->index('start_time');
            // Note: SQLite doesn't support fulltext indexes, will use LIKE queries for search
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('transcriptions');
    }
};
