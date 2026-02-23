# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Minutory is an AI-powered meeting platform built with Laravel 12 and Vue.js 3. Users upload meeting videos, which are transcribed with speaker identification, and can then interact with the content through a conversational AI agent that performs SQL-like searches across all transcriptions.

## Technology Stack

**Backend:** PHP 8.2+, Laravel 12, Inertia.js, MySQL/SQLite, Pest PHP v4, Prism PHP Agent
**Frontend:** Vue.js 3, TypeScript, Inertia.js, Tailwind CSS 4, Vite
**AI:** Prism PHP Agent with custom tools for meeting search

## Development Commands

```bash
# Start full development stack (PHP + Queue + Vite concurrently)
composer dev

# Frontend only
npm run dev

# Production builds
npm run build
npm run build:ssr
```

## Testing

```bash
# Run all tests
composer test
php artisan test

# Run specific test
php artisan test --filter=TestName
```

## Code Quality

```bash
# PHP code formatting (Laravel Pint)
./vendor/bin/pint

# Frontend formatting
npm run format

# Frontend linting
npm run lint

# Check formatting
npm run format:check
```

## Database

```bash
# Run migrations
php artisan migrate

# Fresh migration with seeding
php artisan migrate:fresh --seed

# Create migration
php artisan make:migration create_table_name
```

## Architecture


### Core Domain Models
- **Client**: Company contacts with associated meetings
- **Meeting**: Video uploads with status tracking (pending → processing → completed/failed)
- **Transcription**: Per-segment transcripts with speaker identification and timestamps

### Background Processing
- **TranscribeMeetingJob**: Handles video-to-audio conversion (ffmpeg) and AI transcription (Scriberr)
- Uses Docker containers for processing with proper error handling and retry logic
- Real-time status updates with progress indicators and queue simulation

### AI Integration
- **PrismMeetingSearchTool**: Prism PHP agent tool for cross-meeting content search
- **MeetingSearchTool**: Backend search logic with highlighting and filtering
- Conversational AI interface for natural language queries

### Frontend Architecture
- **Inertia.js** full-stack integration (no API endpoints needed)
- **Vue 3 + TypeScript** components in `resources/js/Pages/`
- **Tailwind CSS 4** for styling with dark mode support
- Real-time status updates without websockets (polling-based)




### Backend Structure

- **Controllers:** `app/Http/Controllers/`
  - `MeetingController` - Meeting CRUD, upload, status tracking
  - `ClientController` - Client CRUD operations
  - `AIAgentController` - AI chat endpoint that integrates with Prism PHP

- **Models:** `app/Models/`
  - `Client` - name, email, company, phone; has many meetings
  - `Meeting` - belongs to client; title, video_path, status (pending/processing/completed/failed), duration, processing timestamps
  - `Transcription` - belongs to meeting; speaker, text, start/end times, confidence
  - `User` - Laravel default user model

- **Jobs:** `app/Jobs/`
  - `TranscribeMeetingJob` - Background job that processes video files. In development, uses fake transcription with Faker. In production, calls Dockerized Python microservice using WhisperX.

- **AI Tools:** `app/Tools/`
  - `MeetingSearchTool` - Static class for searching transcriptions with filters (query, client_id, speaker, limit)
  - `PrismMeetingSearchTool` - Prism PHP Tool wrapper for AI agent integration

### Frontend Structure

- **Pages:** `resources/js/pages/` - Mirror route structure (Dashboard, Clients, Meetings, AI)
- **Shared Components:** `resources/js/lib/` - Reusable Vue components
- **Utilities:** `resources/js/lib/` - Composables like `useRealTimeUpdates.ts` for status polling

### Real-time Features
- Status polling for meeting processing progress
- Progress bars and loading states
- Auto-refresh for status changes without websockets


### Meeting Status Flow

`pending` → `processing` → `completed` or `failed`

The Meeting model includes computed attributes for real-time progress tracking:
- `elapsed_time` - Time since processing started
- `estimated_remaining_time` - Estimated time to completion
- `processing_progress` - Progress percentage (0-100)
- `queue_progress` - Queue position simulation for pending meetings

### AI Agent Integration

The AI agent uses Prism PHP with tool-based architecture:
1. User submits query via `AIAgentController@chat`
2. Prism agent analyzes query and invokes `MeetingSearchTool`
3. Tool searches across all transcriptions with SQL-like filtering
4. Results are formatted with highlighted text, timestamps, and deep links to meetings

### Key Conventions

- Controllers use PascalCase ending with `Controller`
- Models use singular PascalCase
- Vue components use PascalCase filenames
- Frontend TypeScript interfaces use PascalCase (no `I` prefix)
- Use Composition API with `<script setup>` syntax
- Pages in `resources/js/pages/` mirror route structure
- Shared components go in `resources/js/lib/`

### Development Notes

- The transcription microservice (`transcribe-microservice/`) is a Dockerized Python service using WhisperX. In development, `TranscribeMeetingJob` uses fake/simulated transcription.
- Real-time updates are achieved through polling (every 2 seconds) via `useRealTimeUpdates.ts` composable.
- File storage uses Laravel's filesystem; videos stored under `storage/app/meetings/{client_id}/{meeting_id}/`
- Pest v4 is used for testing with browser testing capabilities via Playwright

### Important Context Files

Before starting new work, read:
- `.kiro/steering/tech.md` - Technology stack and commands
- `.kiro/steering/product.md` - Product vision and features
- `.kiro/steering/structure.md` - Project structure conventions
- `.kiro/specs/ai-meeting-platform/design.md` - Detailed design documentation

The `/docs` folder contains comprehensive documentation (100+ files) covering all aspects of the system.


## Background Job Architecture

### Video Processing Pipeline
1. **Upload**: Video stored in `storage/app/public/meetings/`
2. **Queue**: `TranscribeMeetingJob` dispatched to background
3. **Docker Processing**: 
   - ffmpeg container: video → WAV audio
   - Scriberr container: AI transcription with speaker diarization
4. **Storage**: Results in `storage/{meeting_id}/` directory
5. **Database**: Transcription segments with timestamps stored

### Error Handling
- 3 retry attempts with exponential backoff
- User-friendly error messages vs technical logging
- Automatic cleanup of temporary files on failure
- Comprehensive job failure tracking

## AI Agent Integration

### Prism PHP Agent
- **Tool**: `PrismMeetingSearchTool` extends Prism\Tool
- **Search Function**: Cross-meeting full-text search with highlighting
- **Parameters**: query, client_id (optional), speaker filter, result limit
- **Output**: Formatted results with deep links to specific timestamps

### Search Capabilities
- Full-text search across all meeting transcriptions
- Client-specific filtering
- Speaker identification filtering
- Timestamp-based deep linking to video segments
- Confidence score reporting

## Development Notes


### File Storage Strategy
- Videos: `storage/app/public/meetings/{meeting_id}/`
- Temporary processing: `storage/{meeting_id}/` (cleaned up after completion)
- Public access via Laravel storage link
