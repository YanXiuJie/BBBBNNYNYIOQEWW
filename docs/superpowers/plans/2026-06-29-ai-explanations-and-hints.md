# AI Explanations And Hints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace generic question explanations and hints with question-specific step-by-step Bahasa Melayu support, backfill the current question bank, expose explanation where teachers need to audit it, and restart both local services.

**Architecture:** Keep the current `Question` schema and API shape. Strengthen `question_generator.py` and `hint_generator.py` so new AI questions produce explanation and three hint levels, add a small backfill script that updates only support text fields, and make the teacher question bank display explanation previews without changing student practice behavior.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL, SQLite audit scripts, React/Vite, pytest, httpx/OpenAI chat completions.

---

### Task 1: Tests For Specific Explanations And Hints

**Files:**
- Modify: `backend/tests/test_question_generator.py`
- Create: `backend/tests/test_hint_generator.py` additions if needed

- [ ] Add failing tests that reject generic explanation text and require template explanations to contain calculation-specific details from the prompt and expected answer.
- [ ] Add a failing test for AI parsing that accepts optional `hint_level2_ms` and `hint_level3_ms` from the question generator response.
- [ ] Run `pytest tests/test_question_generator.py tests/test_hint_generator.py` and verify the new tests fail before production changes.

### Task 2: Generator Improvements

**Files:**
- Modify: `backend/app/services/question_generator.py`
- Modify: `backend/app/services/hint_generator.py`

- [ ] Update the OpenAI prompt to request `prompt_ms`, `expected_answer`, `hint_ms`, `hint_level2_ms`, `hint_level3_ms`, `explanation_ms`, and `options`.
- [ ] Validate generated text with a helper that rejects empty or generic support text.
- [ ] Change template generation so every branch receives a step-by-step explanation based on the generated prompt, expected answer, hint, and subtopic.
- [ ] Change fallback multilevel hints so they remain tied to the actual question and explanation.
- [ ] Run targeted tests until they pass.

### Task 3: Question Bank Backfill

**Files:**
- Create: `backend/scripts/backfill_question_support_text.py`

- [ ] Back up the current MySQL `questions` table before writing updates.
- [ ] Scan questions where explanation or hints are empty/generic.
- [ ] Use OpenAI to generate replacement `hint_ms`, `hint_level2_ms`, `hint_level3_ms`, and `explanation_ms` from existing prompt, answer, difficulty, and subtopic.
- [ ] Update only support text fields; do not change question prompt, answer, options, difficulty, subtopic, source, or validation status.
- [ ] Print counts only, not API key or full secret values.
- [ ] Re-run the audit to confirm no target generic text remains in MySQL.

### Task 4: Teacher UI Explanation Visibility

**Files:**
- Modify: `frontend/src/pages/teacher/QuestionBank.jsx`

- [ ] Add an Explanation column or compact preview in the teacher Question Bank table.
- [ ] Preserve the existing edit form fields for all hints and explanation.
- [ ] Run `npm run build`.

### Task 5: Final Verification And Restart

**Files:**
- No code files unless verification finds a bug.

- [ ] Run targeted backend tests.
- [ ] Run frontend build.
- [ ] Restart the backend server and frontend Vite server.
- [ ] Report exact local URLs and verification outcomes.
