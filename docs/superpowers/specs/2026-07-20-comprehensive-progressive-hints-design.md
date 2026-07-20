# Comprehensive Practice Progressive Hints Design

**Date:** 2026-07-20

## Goal

Change Comprehensive Practice so that a student remains on the same question while receiving progressively stronger support. The first three wrong answers unlock hints in order. A fourth wrong answer completes the question and reveals the correct answer. Every completed question shows the correct answer and explanation, and the system waits for the student to click the next-question button.

## Confirmed Learning and Scoring Rules

1. A correct first answer completes the question and is recorded as correct.
2. The first wrong answer unlocks hint level 1.
3. The second wrong answer unlocks hint level 2.
4. The third wrong answer unlocks hint level 3.
5. The fourth wrong answer completes the question and reveals the correct answer and explanation.
6. If the student answers correctly after any earlier wrong answer, the question completes immediately but is recorded as incorrect under the outcome `wrong_completed` (`Salah tetapi selesai`).
7. Every completed question displays the correct answer and explanation, including questions answered correctly on the first attempt.
8. The system never moves automatically to the next question. It waits for the student to click `Soalan Seterusnya`.
9. A question contributes exactly one formal result to mastery, attempt history, session progress, and summary statistics.

## Architecture

The backend is authoritative for the active question, wrong-answer count, revealed hints, and completion state. The existing `ComprehensivePracticeSession.state_json` field will store this state, so no database migration is required.

The session state will retain the existing phase result arrays and add an `active_question` object while a question is in progress:

```json
{
  "phase1_results": [],
  "phase2_results": [],
  "phase3_results": [],
  "active_question": {
    "question_id": 123,
    "question_number": 1,
    "phase": "diagnosis",
    "wrong_attempts": 1,
    "attempt_count": 1,
    "first_wrong_answer": "41",
    "revealed_hints": ["basic"],
    "started": true
  }
}
```

`active_question` is cleared only when the question is formally completed. The next call made by the student's `Soalan Seterusnya` button can then select and activate another question.

## Backend Data Flow

### Starting and loading a question

- Starting a comprehensive session initializes `active_question` as null.
- `GET /student/comprehensive-practice/next` returns the existing active question when it has not been completed.
- If there is no active question, the adaptive selector chooses one question, increments the question number once, and saves it as `active_question`.
- Reloading or requesting the current question again must not choose another question or increment progress again.
- The question payload does not expose `expected_answer` to the student before completion.

### Submitting an answer

`POST /student/comprehensive-practice/submit` validates that the submitted question ID matches the session's active question. The backend, not the client, calculates attempt count, wrong-answer count, hints used, and the final scoring outcome.

For an incomplete wrong submission:

- Increment `attempt_count` and `wrong_attempts`.
- Save the first wrong answer when this is the first mistake.
- Add exactly one newly revealed hint according to the wrong-answer count.
- Do not create an `Attempt` row.
- Do not update mastery or style preference.
- Do not append a phase result.
- Return `completed: false` and the newly unlocked hint.

For a completed submission:

- First-attempt correct: final `is_correct` is true and outcome is `correct`.
- Correct after an earlier mistake: final `is_correct` is false and outcome is `wrong_completed`.
- Fourth wrong answer: final `is_correct` is false and outcome is `wrong_completed`.
- Create one `Attempt` row, update mastery once, update style preference once, and append one phase result.
- When the final result is incorrect after multiple submissions, store `first_wrong_answer` in `Attempt.answer_text` so mistake review does not display a correct answer as the student's mistake.
- Use the latest cumulative `time_seconds` value as the total time for the question.
- Derive `hints_used` on the server from the unlocked hint levels rather than trusting the client list.
- Clear `active_question` after the formal result has been saved.
- Return the correct answer and explanation only in this completed response.

## API Response Shape

An incomplete submission returns fields equivalent to:

```json
{
  "completed": false,
  "outcome": "in_progress",
  "attempt_number": 1,
  "wrong_attempts": 1,
  "feedback_ms": "Belum tepat. Cuba lagi dengan petunjuk ini.",
  "revealed_hint": {
    "level": "basic",
    "text_ms": "..."
  }
}
```

A completed submission returns fields equivalent to:

```json
{
  "completed": true,
  "outcome": "correct",
  "is_correct": true,
  "attempt_number": 1,
  "wrong_attempts": 0,
  "feedback_ms": "Betul.",
  "correct_answer": "42",
  "explanation_ms": "...",
  "hints_used": [],
  "mastery_updated": {}
}
```

For a student who made at least one mistake, `outcome` is `wrong_completed` and `is_correct` is false even if a later submitted answer matches the expected answer.

## Frontend Behaviour

- Remove the three manually accessible `Show hint` controls.
- Initially show only the question and answer controls.
- After each incomplete wrong response, clear the selected or typed answer, keep the form enabled, and automatically display the newly unlocked hint.
- Keep all previously unlocked hints visible in their original order.
- Keep the question timer running through all submissions for that question.
- While a submission request is pending, disable the submit button to prevent double clicks.
- When the question completes, stop the timer and lock the answer controls.
- Display `Betul` for `correct` or `Salah tetapi selesai` for `wrong_completed`.
- Always display the standard answer, explanation, attempt count, and number of hints used after completion.
- Display `Soalan Seterusnya` only after completion. Clicking it loads the next question and resets local answer, hint, feedback, and timing state.

## Validation and Error Handling

- Reject submissions for a session not owned by the current student.
- Reject a question ID that does not match the session's active question.
- Reject submissions after the active question has already completed; they must not create duplicate results or mastery updates.
- Preserve the active-question state when an incomplete answer is submitted so a subsequent request resumes the same question.
- Missing hint text should not break the sequence. The existing hint-generation service should ensure all three levels before the question is returned; if a level is still empty, the API should return a safe question-specific fallback.
- Network or API errors remain visible on the current question and must not reset the student's revealed hints or attempt state.

## Testing Strategy

Backend tests will verify:

- Wrong answers 1, 2, and 3 return hint levels 1, 2, and 3 in order.
- The first three wrong answers do not create formal `Attempt` records, update mastery, or increase completed-question totals.
- A fourth wrong answer returns the answer and explanation and records exactly one incorrect result.
- A correct answer after a prior mistake completes with `wrong_completed` and records one incorrect result.
- A correct first answer records one correct result and returns the answer and explanation.
- Hints used are derived from server state.
- Repeated loading during an incomplete question returns the same active question without increasing the question number.
- Invalid, stale, or duplicate submissions do not create extra records.
- The 15-question total and 5/5/5 phase breakdown remain correct.

Frontend verification will confirm:

- Hints cannot be opened before a wrong answer.
- Hints accumulate in the correct order.
- The form remains usable until completion and becomes locked afterward.
- The standard answer and explanation appear for both outcomes.
- No automatic navigation occurs.
- The next-question button resets the UI and requests the next question.
- The production Vite build succeeds.

## Scope

This change applies only to Comprehensive Practice. Diagnostic Test and Adaptive Practice behaviour will not be changed. It reuses the existing three question hint fields and existing session JSON storage, and does not add a database table or migration.
