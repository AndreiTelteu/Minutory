# Minutory — AI Meeting Platform

Minutory is an intelligent AI meeting platform that lets you upload meeting videos, transcribe them automatically, and interact with the content through a conversational AI. It provides synchronized video playback with transcriptions, client organization, real-time processing status, and powerful, SQL-like search across all meetings.

## Key Features

- Meeting transcription from uploaded video files
- Speaker identification with per-segment timestamps
- Action item detection and AI-generated summaries
- Conversational AI agent with SQL-like search over all transcriptions
- Searchable archives across clients, meetings, and timestamps
- Real-time status tracking: pending, processing, completed, failed
- Synchronized video player and transcription navigation
- Filtering by client, date range, and status
- Seamless SPA-like UX with Inertia.js (Laravel + Vue 3)
- Development-focused workflow using MySQL, queues, and fakes

## Screenshots

Note: Placeholder images are linked below. Will replace these with real screenshots as the project evolves.

| ![Dashboard](https://picsum.photos/seed/meetingai-dashboard/1200/700) <br> Dashboard | ![Clients List](https://picsum.photos/seed/meetingai-clients/1200/700) <br> Clients List |
| --- | --- |
| ![Meeting Upload & Processing](https://picsum.photos/seed/meetingai-upload/1200/700) <br> Meeting Upload & Processing | ![Meeting Playback with Transcriptions](https://picsum.photos/seed/meetingai-playback/1200/700) <br> Meeting Playback with Transcriptions |
| ![AI Chat and Search Results](https://picsum.photos/seed/meetingai-ai-chat/1200/700) <br> AI Chat and Search Results |  |

## Architecture Overview

- Frontend: Vue.js 3 + TypeScript, Tailwind CSS 4, Inertia.js (client)
- Backend: Laravel 12, Inertia.js (server), Background Jobs (Queues)
- Data: MySQL, File Storage (videos, thumbnails)
- AI: Prism PHP Agent with a MeetingSearchTool for cross-meeting queries
- Real-time UX: Status badges, progress indicators, and live updates

High-level flow:
1) Upload a meeting video and associate it with a client
2) Backend dispatches a background transcription job and tracks progress
3) On completion, transcriptions are stored with speaker and timestamps
4) Users review meetings with a video player synced to transcription segments
5) AI chat queries perform database-powered searches and return contextual results with deep links

## Tech Stack

- Backend
  - PHP 8.2+
  - Laravel 12
  - Inertia.js (Laravel adapter)
  - MySQL
  - Pest PHP v4 (browser testing)
- Frontend
  - Vue.js 3
  - TypeScript
  - Inertia.js (Vue 3 adapter)
  - Tailwind CSS 4
  - Vite

## Getting Started

Development
```bash
# PHP + Queue + Vite (concurrent dev)
composer dev

# With SSR support
composer dev:ssr

# Frontend only
npm run dev

# Production builds
npm run build
npm run build:ssr
```

Testing
```bash
# Run PHP tests
composer test
php artisan test

# Run a specific test
php artisan test --filter=TestName
```

Code Quality
```bash
# Format PHP code
./vendor/bin/pint

# Format frontend code
npm run format

# Lint frontend code
npm run lint

# Check formatting
npm run format:check
```

Database
```bash
# Run migrations
php artisan migrate

# Fresh migration with seeding
php artisan migrate:fresh --seed

# Create a migration
php artisan make:migration create_table_name
```

Artisan
```bash
# Generate application key
php artisan key:generate

# Clear caches
php artisan config:clear
php artisan cache:clear
php artisan view:clear

# Scaffolding
php artisan make:controller ControllerName
php artisan make:model ModelName
```

## Core Domain Model

- Client: name, email, company, phone; has many meetings
- Meeting: belongs to client; title, video_path, status, duration, timestamps
- Transcription: belongs to meeting; speaker, text, start/end times, confidence

## Status and Roadmap

- Completed
  - Database schema and Eloquent models
  - Client CRUD and UI
  - Meeting upload, validation, and storage
  - Background transcription workflow (fake for dev)
  - Real-time status tracking with progress indicators
  - Video player + transcription sync
  - AI agent integration with MeetingSearchTool
  - Dashboard and navigation

- In Progress / Upcoming
  - Comprehensive integration testing (Pest v4 browser tests)
  - Error handling and UX improvements (uploads, processing failures, network issues)
  - Loading states and robust form validation across async flows

## License

MIT License — see LICENSE.md
