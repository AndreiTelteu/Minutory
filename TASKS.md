# Project Task List

**Status Legend:**
- [ ] : Pending
- [x] : Done

## Core Tasks

- [ ] **Task 1: Project Configuration**
  - Create a MariaDB database for the project.
  - Set up the database credentials in the `.env` file.
  - Run `composer install`.
  - Run `npm install` and `npm run build`.
  - Run database migrations and seeders (`php artisan migrate --seed`).
  - Navigate to `@/transcribe-microservice/` and install dependencies using `uv`.

- [ ] **Task 2: Playwright UI & Functionality Audit**
  - Ensure the local project server is running.
  - Use Playwright to open the local site and autonomously navigate through the project pages to check for issues (UI bugs, broken links, console errors, etc.).
  - **Dynamic Step:** If any issues are found, DO NOT fix them immediately. Instead, add them to this `TASKS.md` file as subtasks under Task 2 (e.g., `- [ ] Task 2.1: Fix issue XYZ...`).
  - For each new subtask added, include: Reproduction steps, expected behavior, and validation steps.

- [ ] **Task 3: Complete TranscribeMeetingJob**
  - Analyze the file `app/Jobs/TranscribeMeetingJob.php`.
  - Identify any incomplete code, missing integrations, or unhandled exceptions.
  - Complete the development and integration within this job file to ensure it properly handles the transcription workflow.

- [ ] **Task 4: End-to-End Transcription Flow Testing**
  - Test the "add new meeting" flow from the browser (via Playwright or appropriate browser automation).
  - Upload the video file located at `~/.openclaw/workspace/demo.mp4` through the browser UI.
  - Wait for and complete the processing flow.
  - **Validation:** Verify that the background AI service successfully generates a correct and complete transcription of the video in the **Romanian language**.



