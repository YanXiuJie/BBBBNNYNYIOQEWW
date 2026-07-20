import { useEffect, useMemo, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";

export default function DiagnosticTest() {
  const [session, setSession] = useState(null);
  const [questionState, setQuestionState] = useState(null);
  const [answer, setAnswer] = useState("");
  const [questionStartedAt, setQuestionStartedAt] = useState(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    startSession().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!questionState?.question || summary) return undefined;
    const intervalId = window.setInterval(() => {
      if (!questionStartedAt) return;
      setElapsedSeconds(Math.max(1, Math.floor((Date.now() - questionStartedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [questionState?.question?.id, questionStartedAt, summary]);

  const progress = useMemo(() => {
    if (!session) return 0;
    const current = questionState?.question_number || session.current_question_number || 0;
    return Math.min(100, Math.round((current / session.total_questions) * 100));
  }, [questionState?.question_number, session]);

  async function startSession() {
    setError("");
    setSummary(null);
    setAnswer("");
    setElapsedSeconds(0);
    const started = await api.startDiagnostic();
    setSession(started);
    await loadNextQuestion(started.session_id);
  }

  async function loadNextQuestion(sessionId) {
    setError("");
    const next = await api.nextDiagnosticQuestion(sessionId);
    if (next.completed) {
      const diagnosticSummary = await api.diagnosticSummary(sessionId);
      setSummary(diagnosticSummary);
      setQuestionState(null);
      setQuestionStartedAt(null);
      return;
    }
    setQuestionState(next);
    setAnswer("");
    setElapsedSeconds(0);
    setQuestionStartedAt(Date.now());
  }

  async function submitAnswer() {
    if (!questionState?.question) return;
    setError("");
    try {
      await api.submitDiagnosticAnswer({
        session_id: questionState.session_id,
        question_id: questionState.question.id,
        answer_text: answer,
        time_seconds: Math.max(1, elapsedSeconds || 1),
      });
      await loadNextQuestion(questionState.session_id);
    } catch (err) {
      setError(err.message);
    }
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!session) return <p>Loading diagnostic...</p>;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Diagnostic Test</p>
        <h2>Ujian Diagnostik Adaptif</h2>
        <p>Soalan dipilih mengikut prestasi semasa untuk menetapkan baseline mastery yang lebih tepat.</p>
      </div>

      {summary ? (
        <>
          <div className="card success-card">
            <h3>Keputusan Diagnostik</h3>
            <p>{summary.summary.correct_count}/{summary.summary.total_questions} betul</p>
            <p>Ketepatan: {summary.summary.accuracy}%</p>
            <button className="secondary-button" onClick={() => startSession().catch((err) => setError(err.message))}>
              Ulang Diagnostik
            </button>
          </div>
          <div className="card">
            <div className="section-header">
              <h3>Ringkasan Mengikut Bab</h3>
            </div>
            <div className="card-grid">
              {summary.chapter_breakdown.map((chapter) => (
                <div className="topic-card" key={chapter.chapter_id}>
                  <strong>{chapter.title_ms}</strong>
                  <span>{chapter.correct}/{chapter.total} betul</span>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : questionState?.question ? (
        <div className="card question-card">
          <div className="question-meta">
            <StatusBadge status={questionState.question.difficulty} />
            <span>Soalan {questionState.question_number}/{session.total_questions}</span>
            <span>Masa: {elapsedSeconds}s</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill primary" style={{ width: `${progress}%` }} />
          </div>
          <p className="eyebrow">{questionState.question.subtopic?.title_ms}</p>
          <h3>{questionState.question.prompt_ms}</h3>
          {questionState.question.question_type === "multiple_choice" ? (
            <div className="option-grid">
              {questionState.question.options.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={answer === option ? "option-button active" : "option-button"}
                  onClick={() => setAnswer(option)}
                >
                  {option}
                </button>
              ))}
            </div>
          ) : (
            <input
              className="input"
              placeholder="Jawapan"
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
            />
          )}
          <div className="pagination-bar">
            <span>{session.chapters.length} bab teras akan diliputi dalam diagnostik ini.</span>
            <button className="primary-button" disabled={!answer.trim()} onClick={submitAnswer}>
              Hantar Jawapan
            </button>
          </div>
        </div>
      ) : (
        <p>Preparing adaptive diagnostic...</p>
      )}
    </section>
  );
}
