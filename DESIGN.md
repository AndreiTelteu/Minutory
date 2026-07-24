# Design

<!-- impeccable:design-schema 1 -->

Direction contract (replacement world, committed 2026-07-25; seed 8ef0f898, standing exit taken):

- **THESIS:** Minutory is a precision tool for a solo professional's private archive. The interface is the category canon played straight — the Linear/Notion class of quiet, exact, keyboard-fast tool UI — refusing the gradient "AI magic" SaaS template. Nothing decorative; every pixel serves scanability and task completion.
- **OWN-WORLD:** Adaptive light/dark. Paper-white and true-ink grounds (never gray-beige, never navy). One indigo accent reserved for primary actions and active states only. Neutral grays tinted cool. 8px card radius, 6px control radius. Hairline borders (1px) declare elevation; shadows appear only on floating layers (dropdowns, toasts). Inter throughout; tabular numerals for timestamps and metrics.
- **STORY:** The user opens the app, sees the state of their archive at a glance, and acts: upload, review, search, ask. The tool disappears into the work.
- **FIRST VIEWPORT:** Left sidebar (workspace identity + nav + theme control), content column with page title and primary action top-right, dense data below. No hero, no marketing chrome.
- **FORM:** Category-standard SaaS tool shell. Canon peers: Linear (precision, restraint, speed), Notion (calm surfaces, humane spacing). Executed without irony or smuggled quirk.

## Grounds

Light: `#ffffff` app ground, `#fafafa` sidebar/subtle ground. Dark: `#0f0f10` app ground, `#171718` sidebar/subtle ground, `#1f1f21` raised. Both themes are first-class; dark is not an afterthought inversion. Follows `prefers-color-scheme`; a toggle in the sidebar overrides and persists to localStorage.

## Color Roles

| Role | Light | Dark | Use |
|---|---|---|---|
| ground | white | `#0f0f10` | app background |
| ground-subtle | `#fafafa` | `#171718` | sidebar, wells, table headers |
| ground-raised | white | `#1f1f21` | cards, dropdowns |
| border | `#e5e5e4` | `#2a2a2d` | hairlines, card edges |
| border-strong | `#d4d4d2` | `#3a3a3e` | inputs, dividers needing emphasis |
| ink | `#18181b` | `#ededec` | primary text |
| ink-secondary | `#52525b` | `#a1a1aa` | secondary text, labels |
| ink-tertiary | `#71717a` | `#8a8a90` | placeholders, metadata (≥4.5:1 on ground) |
| accent | `#4f46e5` (indigo-600) | `#818cf8` (indigo-400) | text-level: links, active nav, focus rings, icons |
| accent-hover | `#4338ca` | `#a5b4fc` | text-level hover |
| accent-solid | `#4f46e5` | `#4f46e5` | filled buttons, user chat bubbles (white text ≥4.5:1 both themes) |
| accent-solid-hover | `#4338ca` | `#5b53e9` | filled button hover |
| accent-subtle | `#eef2ff` | indigo-400/12% | active nav background, selected rows |

Status colors stay semantic: completed=green-600/400, processing=amber-600/400, pending=zinc-500, failed=red-600/400. Accent is never used for status.

## Typography

Inter (400/500/600/700) via Bunny Fonts. UI base 14px. Page titles 20px/600. Section headers 13px/600 uppercase-tracked labels are banned except in table headers (11px/500/0.05em uppercase is the canon there). Timestamps, durations, and metrics use `font-variant-numeric: tabular-nums`. No display face, no serif, no mono costume.

## Components

- **Buttons:** 6px radius, 8px/14px padding, 13-14px/500. Primary = accent fill, white text. Secondary = transparent, 1px border-strong border, ink text. Ghost = text-only, hover ground-subtle. Disabled = 50% opacity, no color change.
- **Inputs:** 6px radius, border-strong border, ground-raised fill, focus = 2px accent ring (offset 0), error = red border + red-600 message below.
- **Cards/panels:** ground-raised, 1px border, 8px radius, no shadow. Never nest cards.
- **Tables:** header row ground-subtle with 11px uppercase labels, row hairlines, hover ground-subtle, no vertical borders.
- **Status badges:** 12px/500 pill with dot, tinted text on tinted ground at 8-12% opacity, 999px radius (pills allowed for badges only).
- **Sidebar:** 240px, ground-subtle, hairline right border. Nav items 13px/500, 6px radius, icon+label, active = accent-subtle ground + accent text. Workspace name top, theme toggle bottom.
- **Toasts:** ground-raised, 1px border, 8px radius, single soft shadow (0 4px 12px rgb(0 0 0 / 0.08) light / 0.24 dark), status-colored icon only.

## Motion

One motion language: 150-200ms ease-out for hovers and state changes, 250-300ms for entrances (slide+fade). No spring physics, no staggered reveals, no scroll animation. Progress indicators animate honestly from polled data. Spinners only for indeterminate waits.

## Sacred Behavior (do not regress)

- Video ↔ transcript sync (click-to-seek, auto-highlight, auto-scroll) on Meetings/Show.
- Live polling updates (2s) on Meetings/Index and Meetings/Show pending/processing states.
- Upload drag-drop with progress and retry on Meetings/Create.
- AI chat conversation flow with search-result cards and deep links.

## Bans (this project)

- No gradients (fills or text), no glass/backdrop-blur decoration, no glows.
- No colored border-left accents on cards or list items.
- No hero metric cards with big numbers as page structure (stats render as a quiet inline strip).
- No emoji in UI chrome (icons are 16px outline strokes, 1.5px).
- No uppercase tracked eyebrows outside table headers.
