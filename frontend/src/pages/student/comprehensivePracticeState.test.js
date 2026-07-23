import test from "node:test";
import assert from "node:assert/strict";

import {
  applySubmissionResponse,
  createQuestionInteraction,
} from "./comprehensivePracticeState.js";


test("creates an empty interaction for a new question", () => {
  assert.deepEqual(createQuestionInteraction(), {
    answer: "",
    feedback: null,
    result: null,
    revealedHints: [],
  });
});


test("an incomplete response clears the answer and appends one hint", () => {
  const next = applySubmissionResponse(
    {
      answer: "41",
      feedback: null,
      result: null,
      revealedHints: [],
    },
    {
      completed: false,
      feedback_ms: "Belum tepat.",
      revealed_hint: { level: "basic", text_ms: "Hint 1" },
    },
  );

  assert.deepEqual(next, {
    answer: "",
    feedback: "Belum tepat.",
    result: null,
    revealedHints: [{ level: "basic", text_ms: "Hint 1" }],
  });
});


test("repeated hint levels are not duplicated", () => {
  const next = applySubmissionResponse(
    {
      answer: "40",
      feedback: "Belum tepat.",
      result: null,
      revealedHints: [{ level: "basic", text_ms: "Hint 1" }],
    },
    {
      completed: false,
      feedback_ms: "Cuba lagi.",
      revealed_hint: { level: "basic", text_ms: "Hint 1" },
    },
  );

  assert.equal(next.revealedHints.length, 1);
});


test("a completed response preserves hints and stores the result", () => {
  const response = {
    completed: true,
    outcome: "wrong_completed",
    correct_answer: "42",
    explanation_ms: "40 + 2 = 42",
  };
  const next = applySubmissionResponse(
    {
      answer: "42",
      feedback: "Belum tepat.",
      result: null,
      revealedHints: [{ level: "basic", text_ms: "Hint 1" }],
    },
    response,
  );

  assert.equal(next.answer, "42");
  assert.equal(next.feedback, null);
  assert.equal(next.result, response);
  assert.equal(next.revealedHints.length, 1);
});
