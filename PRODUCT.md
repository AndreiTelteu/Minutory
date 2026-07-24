# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

A solo professional (consultant, freelancer, or independent operator) who records client calls and needs a private, searchable knowledge base of everything said. They work alone, manage their own infrastructure, and treat meeting recordings as working material — not content to share with a team.

## Product Purpose

Minutory turns meeting recordings into a queryable private archive. Upload a video, get a speaker-identified transcript, then ask questions across every meeting you've ever recorded. Success means never re-watching a recording to find what someone said — you just ask.

## Positioning

Self-hosted meeting intelligence. Unlike Otter.ai, Fireflies, or tl;dv, Minutory runs entirely on the user's own infrastructure. No third-party SaaS touches the recordings or transcripts. The AI search is the interaction layer; privacy is the reason it exists.

## Operating Context

- Solo workflow: one user, no collaboration features, no sharing
- Meetings organized by client relationship, not chronology
- Background processing: upload → queue → transcription → ready (minutes, not seconds)
- The user checks back later; real-time status polling bridges the wait
- Infrastructure: Laravel + queue worker + Docker microservice (WhisperX) + ffmpeg, all self-managed
- The AI agent (Prism PHP via OpenRouter) is the primary search interface; direct search is a fallback

## Capabilities and Constraints

- Video upload (MP4, MOV, AVI, WebM; up to 500 MB) with client-side validation and retry
- Automatic transcription with speaker diarization (WhisperX in Docker)
- Synchronized video + transcript playback with click-to-seek
- Conversational AI search across all transcriptions with deep links to timestamps
- Client CRUD to organize meetings by relationship
- Status polling (2s interval) for processing progress — no websockets
- Rate-limited AI chat (10 req/min per IP)
- The nav currently renders "MeetingAI" — this is a placeholder; the product name is Minutory

## Brand Commitments

- Name: Minutory. The "MeetingAI" text in the nav is a placeholder to be replaced.
- Visual direction: category-standard tool UI played straight (user decision, 2026-07-25). Craft bar: Linear and Notion. No experimental visual world; execute convention at full fidelity.
- Adaptive light/dark, following system preference.
- Sacred behavior: video↔transcript sync and live polling updates must survive every redesign.

## Evidence on Hand

- Fully functional core loop: upload → transcribe → review → AI search
- 16 shared Vue components, well-typed TypeScript throughout
- 124 documentation files in /docs
- Pest v4 test suite with Playwright browser tests
- No logo, no brand colors, no design tokens — the UI is unthemed Tailwind defaults
- No real customer testimonials, case studies, or press to reference

## Product Principles

1. **Privacy is the product.** Every architectural decision serves the guarantee that recordings never leave the user's machine.
2. **One person, zero friction.** No teams, no permissions, no onboarding ceremony. Upload and go.
3. **The archive compounds.** Each meeting makes every previous meeting more searchable. The system gets more valuable with use.
4. **Transcripts are the interface.** The video is evidence; the transcript is the working surface. Design for reading and searching text, not watching video.
5. **Earn trust through craft.** A solo professional betting on self-hosted software needs to feel the tool is reliable and considered, not a hobby project.
