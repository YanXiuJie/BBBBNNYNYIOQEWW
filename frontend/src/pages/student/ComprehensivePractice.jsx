import { useEffect, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";
import PracticeSummary from "./PracticeSummary";
import {
  applySubmissionResponse,
  createQuestionInteraction,
} from "./comprehensivePracticeState.js";

const PHASE_LABELS = {
  diagnosis: "Diagnostik",
  remedial: "Pemulihan",
  consolidation: "Pengukuhan",
};

export default function ComprehensivePractice() {
  const [sessionId, setSessionId] = useState(null);
  const [data, setData] = useState(null);
  const [interaction, setInteraction] = useState(createQuestionInteraction);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [startedAt, setStartedAt] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(0);
  const [error, setError] = useState("");
  const [isStarting, setIsStarting] = useState(false);
  const [isLoadingQuestion, setIsLoadingQuestion] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

  const {
    answer,
    feedback: attemptFeedback,
    result,
    revealedHints,
  } = interaction;

  async function startSession() {
    setError("");
    setShowSummary(false);
    setIsStarting(true);
    try {
      const sessionData = await api.startComprehensivePractice();
      setSessionId(sessionData.session_id);
      setQuestionNumber(0);
      await loadNextQuestion(sessionData.session_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsStarting(false);
    }
  }

  async function loadNextQuestion(sid) {
    setError("");
    setIsLoadingQuestion(true);
    try {
      const nextData = await api.getNextComprehensiveQuestion(sid);
      if (nextData.completed) {
        setData(null);
        setStartedAt(null);
        setShowSummary(true);
        return;
      }
      setData(nextData);
      setQuestionNumber(nextData.question_number);
      setInteraction({
        answer: "",
        feedback: null,
        result: null,
        revealedHints: nextData.revealed_hints || [],
      });
      setElapsedSeconds(0);
      setStartedAt(Date.now());
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoadingQuestion(false);
    }
  }

  useEffect(() => {
    if (!startedAt || result) return undefined;
    const intervalId = window.setInterval(() => {
      setElapsedSeconds(
        Math.max(1, Math.floor((Date.now() - startedAt) / 1000)),
      );
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [startedAt, result]);

  async function submit(event) {
    event.preventDefault();
    if (!data?.question || !sessionId || isSubmitting || result) return;
    setError("");
    setIsSubmitting(true);
    const secondsSpent = Math.max(
      1,
      elapsedSeconds ||
        (startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 1),
    );
    try {
      const submitResult = await api.submitComprehensiveAnswer({
        session_id: sessionId,
        question_id: data.question.id,
        answer_text: answer,
        time_seconds: secondsSpent,
      });
      setInteraction((current) =>
        applySubmissionResponse(current, submitResult),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function continueSession() {
    loadNextQuestion(sessionId);
  }

  function resetSession() {
    setSessionId(null);
    setShowSummary(false);
    setData(null);
    setInteraction(createQuestionInteraction());
    setQuestionNumber(0);
    setElapsedSeconds(0);
    setStartedAt(null);
    setError("");
  }

  if (showSummary && sessionId) {
    return (
      <PracticeSummary
        sessionId={sessionId}
        onRestart={resetSession}
      />
    );
  }

  if (!sessionId) {
    return (
      <section className="page-stack">
        <div className="page-title">
          <p className="eyebrow">Latihan Menyeluruh</p>
          <h2>Comprehensive Practice</h2>
        </div>
        {error && <p className="error-text" role="alert">{error}</p>}
        <div className="card">
          <h3>Latihan Menyeluruh Matematik Tahun 5</h3>
          <p>Sistem akan memilih 15 soalan secara adaptif merentas tiga fasa.</p>
          <button
            className="primary-button"
            onClick={startSession}
            disabled={isStarting}
          >
            {isStarting ? "Memulakan..." : "Mulakan Latihan"}
          </button>
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="page-stack">
        <div className="page-title">
          <p className="eyebrow">Latihan Menyeluruh</p>
          <h2>Comprehensive Practice</h2>
        </div>
        {error ? (
          <>
            <p className="error-text" role="alert">{error}</p>
            <button
              className="primary-button"
              onClick={() => loadNextQuestion(sessionId)}
              disabled={isLoadingQuestion}
            >
              {isLoadingQuestion ? "Memuatkan..." : "Cuba Lagi"}
            </button>
          </>
        ) : (
          <p>Memuatkan soalan...</p>
        )}
      </section>
    );
  }

  const isMultipleChoice = data.question.question_type === "multiple_choice";
  const answerControlsDisabled = Boolean(result) || isSubmitting;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Latihan Menyeluruh</p>
        <h2>{data.question.subtopic?.title_ms || "Matematik Tahun 5"}</h2>
      </div>

      {error && <p className="error-text" role="alert">{error}</p>}

      <div className="card question-card">
        <div className="question-meta">
          <StatusBadge status={data.question.difficulty} />
          <span>Fasa: {PHASE_LABELS[data.phase] || data.phase}</span>
          <span>Soalan {questionNumber}/15</span>
          <span>Masa: {elapsedSeconds}s</span>
        </div>

        <h3>{data.question.prompt_ms}</h3>

        {revealedHints.length > 0 && (
          <div className="hints-section" aria-live="polite">
            {revealedHints.map((hint, index) => (
              <div
                key={hint.level}
                className="hint-item progressive-hint"
              >
                <strong>Petunjuk {index + 1}</strong>
                <p className="hint-box">{hint.text_ms}</p>
              </div>
            ))}
          </div>
        )}

        {attemptFeedback && !result && (
          <p className="retry-feedback" role="status">
            {attemptFeedback}
          </p>
        )}

        <form className="form-grid" onSubmit={submit}>
          {isMultipleChoice ? (
            <div className="wide-field option-grid">
              {data.question.options.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={
                    answer === option
                      ? "option-button active"
                      : "option-button"
                  }
                  disabled={answerControlsDisabled}
                  onClick={() =>
                    setInteraction((current) => ({
                      ...current,
                      answer: option,
                    }))
                  }
                >
                  {option}
                </button>
              ))}
            </div>
          ) : (
            <label>
              Jawapan
              <input
                className="input"
                value={answer}
                disabled={answerControlsDisabled}
                onChange={(event) =>
                  setInteraction((current) => ({
                    ...current,
                    answer: event.target.value,
                  }))
                }
              />
            </label>
          )}
          <button
            className="primary-button"
            disabled={!answer.trim() || answerControlsDisabled}
          >
            {isSubmitting ? "Menyemak..." : "Hantar"}
          </button>
        </form>
      </div>

      {result && (
        <div
          className={
            result.outcome === "correct"
              ? "card success-card"
              : "card danger-card"
          }
        >
          <h3>
            {result.outcome === "correct"
              ? "Betul"
              : "Salah tetapi selesai"}
          </h3>
          <p>{result.feedback_ms}</p>
          <div className="answer-review">
            <p>
              <strong>Jawapan betul:</strong> {result.correct_answer}
            </p>
            <p>
              <strong>Penjelasan:</strong> {result.explanation_ms}
            </p>
          </div>
          <p>
            Cubaan: {result.attempt_number} | Petunjuk digunakan:{" "}
            {(result.hints_used || []).length}
          </p>
          <button
            className="primary-button"
            onClick={continueSession}
            disabled={isLoadingQuestion}
          >
            {isLoadingQuestion ? "Memuatkan..." : "Soalan Seterusnya"}
          </button>
        </div>
      )}
    </section>
  );
}
