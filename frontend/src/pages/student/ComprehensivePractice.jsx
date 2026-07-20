import { useEffect, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";
import PracticeSummary from "./PracticeSummary";

const PHASE_LABELS = {
  diagnosis: "Diagnostik",
  remedial: "Pemulihan",
  consolidation: "Pengukuhan",
};

export default function ComprehensivePractice() {
  const [sessionId, setSessionId] = useState(null);
  const [data, setData] = useState(null);
  const [answer, setAnswer] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [startedAt, setStartedAt] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [hintsUsed, setHintsUsed] = useState([]);
  const [expandedHintLevel, setExpandedHintLevel] = useState(null);
  const [isStarting, setIsStarting] = useState(false);
  const [showSummary, setShowSummary] = useState(false);

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
    setResult(null);
    setAnswer("");
    setHintsUsed([]);
    setExpandedHintLevel(null);
    setElapsedSeconds(0);
    try {
      const nextData = await api.getNextComprehensiveQuestion(sid);
      if (nextData.completed) {
        setData(null);
        setShowSummary(true);
        return;
      }
      setData(nextData);
      setQuestionNumber(nextData.question_number);
      setStartedAt(Date.now());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (!startedAt || result) return undefined;
    const intervalId = window.setInterval(() => {
      setElapsedSeconds(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [startedAt, result]);

  async function submit(event) {
    event.preventDefault();
    if (!data?.question || !sessionId) return;
    setError("");
    const secondsSpent = Math.max(1, elapsedSeconds || (startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 1));
    try {
      const submitResult = await api.submitComprehensiveAnswer({
        session_id: sessionId,
        question_id: data.question.id,
        answer_text: answer,
        time_seconds: secondsSpent,
        hints_used: hintsUsed,
      });
      setResult(submitResult);
    } catch (err) {
      setError(err.message);
    }
  }

  function continueSession() {
    loadNextQuestion(sessionId);
  }

  function toggleHint(level) {
    setExpandedHintLevel(expandedHintLevel === level ? null : level);
    if (!hintsUsed.includes(level)) {
      setHintsUsed([...hintsUsed, level]);
    }
  }

  if (error) return <p className="error-text">{error}</p>;

  if (showSummary && sessionId) {
    return (
      <PracticeSummary
        sessionId={sessionId}
        onRestart={() => {
          setSessionId(null);
          setShowSummary(false);
          setData(null);
          setResult(null);
        }}
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
        <div className="card">
          <h3>Latihan Menyeluruh Matematik Tahun 5</h3>
          <p>Sistem akan memilih 15 soalan secara adaptif merentas tiga fasa.</p>
          <button className="primary-button" onClick={startSession} disabled={isStarting}>
            {isStarting ? "Memulakan..." : "Mulakan Latihan"}
          </button>
        </div>
      </section>
    );
  }

  if (!data) return <p>Memuatkan soalan...</p>;

  const isMultipleChoice = data.question.question_type === "multiple_choice";

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Latihan Menyeluruh</p>
        <h2>{data.question.subtopic?.title_ms || "Matematik Tahun 5"}</h2>
      </div>

      <div className="card question-card">
        <div className="question-meta">
          <StatusBadge status={data.question.difficulty} />
          <span>Fasa: {PHASE_LABELS[data.phase] || data.phase}</span>
          <span>Soalan {questionNumber}/15</span>
          <span>Masa: {elapsedSeconds}s</span>
        </div>

        <h3>{data.question.prompt_ms}</h3>

        <div className="hints-section">
          {[["basic", data.hint_config.hint_level1_ms], ["intermediate", data.hint_config.hint_level2_ms], ["detailed", data.hint_config.hint_level3_ms]].map(
            ([level, text]) =>
              text ? (
                <div key={level} className="hint-item">
                  <button className="hint-toggle" type="button" onClick={() => toggleHint(level)} disabled={Boolean(result)}>
                    {expandedHintLevel === level ? "Hide" : "Show"} hint
                  </button>
                  {expandedHintLevel === level && <p className="hint-box">{text}</p>}
                </div>
              ) : null,
          )}
        </div>

        <form className="form-grid" onSubmit={submit}>
          {isMultipleChoice ? (
            <div className="wide-field option-grid">
              {data.question.options.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={answer === option ? "option-button active" : "option-button"}
                  disabled={Boolean(result)}
                  onClick={() => setAnswer(option)}
                >
                  {option}
                </button>
              ))}
            </div>
          ) : (
            <label>
              Jawapan
              <input className="input" value={answer} disabled={Boolean(result)} onChange={(event) => setAnswer(event.target.value)} />
            </label>
          )}
          <button className="primary-button" disabled={!answer.trim() || Boolean(result)}>
            Hantar
          </button>
        </form>
      </div>

      {result && (
        <div className={result.is_correct ? "card success-card" : "card danger-card"}>
          <h3>{result.is_correct ? "Betul" : "Belum tepat"}</h3>
          <p>{result.feedback_ms}</p>
          {hintsUsed.length > 0 && <p>Petunjuk digunakan: {hintsUsed.length}</p>}
          <button className="primary-button" onClick={continueSession}>
            Soalan Seterusnya
          </button>
        </div>
      )}
    </section>
  );
}
