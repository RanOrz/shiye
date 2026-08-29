# Local Web Clipper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Chrome extension and localhost service that clip the current page or transcribe a media URL into locally saved Markdown.

**Architecture:** A Manifest V3 extension owns the two-tab UI and page extraction. A Flask service bound to `127.0.0.1` owns configuration, authenticated file writes, optional AI organization, and queued media transcription.

**Tech Stack:** Chrome Manifest V3, vanilla HTML/CSS/JavaScript, Python 3.11, Flask, yt-dlp, youtube-transcript-api, Whisper, FFmpeg, unittest.

---

### Task 1: Project foundation and configuration

**Files:**
- Create: `.gitignore`
- Create: `server/__init__.py`
- Create: `server/config_store.py`
- Test: `server/tests/test_config_store.py`

**Steps:**
1. Write tests for default settings, token creation, safe persistence and `0600` permissions.
2. Run `python -m unittest server.tests.test_config_store -v`; expect failure because the module is absent.
3. Implement `ConfigStore` with atomic JSON writes and environment overrides.
4. Rerun the focused test; expect pass.
5. Commit the foundation.

### Task 2: Markdown rendering and safe local writes

**Files:**
- Create: `server/services/markdown_service.py`
- Create: `server/services/storage_service.py`
- Test: `server/tests/test_markdown_storage.py`

**Steps:**
1. Write tests for YAML quoting, page/media templates, filename sanitization, subdirectory containment and duplicate names.
2. Run the focused test; expect import failures.
3. Implement deterministic renderers and contained file writes.
4. Rerun tests; expect pass.
5. Commit the storage slice.

### Task 3: Optional AI organization

**Files:**
- Create: `server/services/ai_service.py`
- Test: `server/tests/test_ai_service.py`

**Steps:**
1. Write tests for disabled mode, malformed responses, OpenAI-compatible responses and Ollama responses using mocks.
2. Run the focused test; expect failure.
3. Implement provider adapters with timeouts and JSON-only structured results.
4. Rerun tests; expect pass.
5. Commit the AI slice.

### Task 4: Media transcription pipeline

**Files:**
- Create: `server/services/media_service.py`
- Create: `server/job_manager.py`
- Test: `server/tests/test_media_service.py`
- Test: `server/tests/test_job_manager.py`

**Steps:**
1. Write tests for YouTube ID parsing, subtitle-first behavior, fallback selection, URL validation and job transitions.
2. Run focused tests; expect failure.
3. Implement metadata lookup, subtitle fetch, temporary audio download, lazy Whisper loading and cleanup.
4. Implement a single-worker in-memory queue with stable status payloads.
5. Rerun tests; expect pass and no network calls.
6. Commit the media slice.

### Task 5: Local HTTP API

**Files:**
- Create: `server/app.py`
- Test: `server/tests/test_app.py`

**Steps:**
1. Write Flask client tests for health, pairing, authorization, settings, folder configuration, page save and media jobs.
2. Run the focused test; expect failure.
3. Implement extension-origin CORS, token checks and JSON endpoints.
4. Rerun tests; expect pass.
5. Commit the API slice.

### Task 6: Chrome extension shell and page clipper

**Files:**
- Create: `extension/manifest.json`
- Create: `extension/popup.html`
- Create: `extension/popup.css`
- Create: `extension/popup.js`
- Create: `extension/page-extractor.js`

**Steps:**
1. Add the Manifest V3 action, `activeTab`, `scripting`, `storage`, and localhost host permission.
2. Build a compact single-input popup with saved-folder switching, a gear-only settings action, and accessible status states.
3. Implement metadata extraction, DOM cleanup and HTML-to-Markdown conversion.
4. Implement pairing, current-page URL shortcut,正文预览, automatic page/media routing, save action and job resume.
5. Run `node --check` on JavaScript files; expect pass.
6. Commit the popup slice.

### Task 7: Extension settings

**Files:**
- Create: `extension/options.html`
- Create: `extension/options.css`
- Create: `extension/options.js`

**Steps:**
1. Build save-folder, subdirectory, Whisper and AI provider controls.
2. Connect folder chooser and settings APIs without exposing saved API keys.
3. Add connection and validation feedback.
4. Run JavaScript syntax checks; expect pass.
5. Commit the settings slice.

### Task 8: Startup, documentation and end-to-end verification

**Files:**
- Create: `requirements.txt`
- Create: `start.command`
- Create: `README.md`

**Steps:**
1. Add dependency and startup instructions without embedding secrets.
2. Run `python -m unittest discover -s server/tests -v`; expect all pass.
3. Run `node --check extension/*.js`; expect all pass.
4. Start the service against a temporary save directory and verify health, pairing and Markdown output with curl.
5. Serve extension pages locally for browser visual inspection; fix all visible issues.
6. Run `git status --short` and review the final diff.
7. Commit the verified MVP.
