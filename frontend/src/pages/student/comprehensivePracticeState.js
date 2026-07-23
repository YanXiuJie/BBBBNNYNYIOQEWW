export function createQuestionInteraction() {
  return {
    answer: "",
    feedback: null,
    result: null,
    revealedHints: [],
  };
}


export function applySubmissionResponse(interaction, response) {
  if (response.completed) {
    return {
      ...interaction,
      feedback: null,
      result: response,
    };
  }

  const nextHints = [...interaction.revealedHints];
  const revealedHint = response.revealed_hint;
  if (
    revealedHint &&
    !nextHints.some((hint) => hint.level === revealedHint.level)
  ) {
    nextHints.push(revealedHint);
  }

  return {
    ...interaction,
    answer: "",
    feedback: response.feedback_ms,
    result: null,
    revealedHints: nextHints,
  };
}
