import { useEffect, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";

const SESSION_LIMIT = 10;

export default function AdaptivePractice({ subtopicId }) {
  const [data, setData] = useState(null);
  const [fallbackSubtopicId, setFallbackSubtopicId] = useState(null);
  const [answer, setAnswer] = useState("");
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [startedAt, setStartedAt] = useState(null);
  const [questionNumber, setQuestionNumber] = useState(1);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const effectiveSubtopicId = subtopicId || fallbackSubtopicId;

  async function loadQuestion(nextQuestionNumber = 1, targetSubtopicId = effectiveSubtopicId) {
    if (!targetSubtopicId) return;
    setError("");
    setResult(null);
    setAnswer("");
    setShowHint(false);
    setElapsedSeconds(0);
    setSessionComplete(false);
    try {
      const nextData = await api.nextQuestion(targetSubtopicId);
      setData(nextData);
      setQuestionNumber(nextQuestionNumber);
      setStartedAt(Date.now());
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (subtopicId) {
      setFallbackSubtopicId(null);
      return undefined;
    }

    let active = true;
    api.syllabus()
      .then((body) => {
        const firstSubtopic = body.chapters.flatMap((chapter) => chapter.subtopics || [])[0];
        if (active) setFallbackSubtopicId(firstSubtopic?.id || null);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });

    return () => {
      active = false;
    };
  }, [subtopicId]);

  useEffect(() => {
    if (!effectiveSubtopicId) return;
    loadQuestion(1, effectiveSubtopicId);
  }, [effectiveSubtopicId]);

  useEffect(() => {
    if (!startedAt || result) return undefined;
    const intervalId = window.setInterval(() => {
      setElapsedSeconds(Math.max(1, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [startedAt, result]);

  async function submit(event) {
    event.preventDefault();
    if (!data?.question) return;
    setError("");
    const secondsSpent = Math.max(1, elapsedSeconds || (startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 1));
    try {
      setResult(await api.submitAttempt({
        question_id: data.question.id,
        answer_text: answer,
        time_seconds: secondsSpent,
      }));
    } catch (err) {
      setError(err.message);
    }
  }

  function continueSession() {
    if (questionNumber >= SESSION_LIMIT) {
      setSessionComplete(true);
      setStartedAt(null);
      return;
    }
    loadQuestion(questionNumber + 1);
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!effectiveSubtopicId) return <p>Loading topic...</p>;
  if (!data) return <p>Loading question...</p>;
  if (sessionComplete) {
    return (
      <section className="page-stack">
        <div className="page-title">
          <p className="eyebrow">Adaptive Practice</p>
          <h2>{data.question.subtopic?.title_ms}</h2>
        </div>
        <div className="card success-card">
          <h3>Sesi latihan selesai</h3>
          <p>Anda telah menjawab {SESSION_LIMIT} soalan dalam sesi ini.</p>
          <button className="primary-button" onClick={() => loadQuestion(1, effectiveSubtopicId)}>Mulakan Sesi Baru</button>
        </div>
      </section>
    );
  }

  const isMultipleChoice = data.question.question_type === "multiple_choice";

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Adaptive Practice</p>
        <h2>{data.question.subtopic?.title_ms}</h2>
      </div>
      <div className="card question-card">
        <div className="question-meta">
          <StatusBadge status={data.recommended_difficulty} />
          <span>Soalan {questionNumber}/{SESSION_LIMIT}</span>
          <span>Mastery: {Math.round(data.mastery.score)}%</span>
          <span>Masa: {elapsedSeconds}s</span>
        </div>
        <h3>{data.question.prompt_ms}</h3>
        <button className="secondary-button" onClick={() => setShowHint(!showHint)}>
          {showHint ? "Sembunyi Petunjuk" : "Tunjuk Petunjuk"}
        </button>
        {showHint && <p className="hint-box">{data.question.hint_ms}</p>}
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
          <button className="primary-button" disabled={!answer.trim() || Boolean(result)}>Hantar</button>
        </form>
      </div>
      {result && (
        <div className={result.is_correct ? "card success-card" : "card danger-card"}>
          <h3>{result.is_correct ? "Betul" : "Belum tepat"}</h3>
          <p>{result.feedback_ms}</p>
          <button className="primary-button" onClick={continueSession}>
            {questionNumber >= SESSION_LIMIT ? "Tamat Sesi" : "Soalan Seterusnya"}
          </button>
        </div>
      )}
    </section>
  );
}
