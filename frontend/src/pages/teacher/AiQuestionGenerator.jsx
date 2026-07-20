import { useEffect, useMemo, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";

const difficultyRules = {
  easy: "One-step question with smaller numbers.",
  medium: "Two-step question or mixed units.",
  hard: "Multi-step question with an extra condition such as interest, comparison or larger values.",
};

export default function AiQuestionGenerator() {
  const [chapters, setChapters] = useState([]);
  const [chapterId, setChapterId] = useState(null);
  const [subtopicId, setSubtopicId] = useState(null);
  const [difficulty, setDifficulty] = useState("medium");
  const [questionType, setQuestionType] = useState("short_answer");
  const [generated, setGenerated] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .syllabus()
      .then((body) => {
        setChapters(body.chapters);
        const firstChapter = body.chapters.find((chapter) => chapter.subtopics?.length);
        if (firstChapter) {
          setChapterId(firstChapter.id);
          setSubtopicId(firstChapter.subtopics[0].id);
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  const selectedChapter = useMemo(
    () => chapters.find((chapter) => chapter.id === Number(chapterId)),
    [chapters, chapterId],
  );

  async function generate() {
    setError("");
    if (!chapterId || !subtopicId) {
      setError("Sila pilih chapter dan subtopic dahulu.");
      return;
    }
    try {
      const body = await api.generateQuestion({
        chapter_id: Number(chapterId),
        subtopic_id: Number(subtopicId),
        difficulty,
        question_type: questionType,
      });
      setGenerated(body.question);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">AI Question Generator</p>
        <h2>Generate Malay Math Question</h2>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="card form-grid">
        <label>
          Chapter
          <select className="select" value={chapterId ?? ""} onChange={(event) => {
            const nextChapter = chapters.find((chapter) => chapter.id === Number(event.target.value));
            setChapterId(Number(event.target.value));
            setSubtopicId(nextChapter?.subtopics?.[0]?.id || null);
          }}>
            {chapters.map((chapter) => <option key={chapter.id} value={chapter.id}>{chapter.number}. {chapter.title_ms}</option>)}
          </select>
        </label>
        <label>
          Subtopic
          <select className="select" value={subtopicId ?? ""} onChange={(event) => setSubtopicId(Number(event.target.value))}>
            {(selectedChapter?.subtopics || []).map((subtopic) => <option key={subtopic.id} value={subtopic.id}>{subtopic.title_ms}</option>)}
          </select>
        </label>
        <label>
          Difficulty
          <select className="select" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
          <small className="form-help">{difficultyRules[difficulty]}</small>
        </label>
        <label>
          Question type
          <select className="select" value={questionType} onChange={(event) => setQuestionType(event.target.value)}>
            <option value="short_answer">Short answer</option>
            <option value="multiple_choice">Multiple choice</option>
          </select>
        </label>
        <button className="primary-button" onClick={generate} disabled={!chapterId || !subtopicId}>Generate & Save</button>
      </div>
      {generated && (
        <div className="card">
          <div className="question-meta">
            <StatusBadge status={generated.difficulty} />
            <StatusBadge status={generated.question_type} />
            <StatusBadge status={generated.validation_status} />
          </div>
          <h3>{generated.prompt_ms}</h3>
          <p>Answer: <strong>{generated.expected_answer}</strong></p>
          {generated.options?.length > 0 && (
            <div className="options-list">
              {generated.options.map((option) => <span key={option}>{option}</span>)}
            </div>
          )}
          <p>Hint 1: {generated.hint_ms}</p>
          <p>Hint 2: {generated.hint_level2_ms || "-"}</p>
          <p>Hint 3: {generated.hint_level3_ms || "-"}</p>
          <p>{generated.explanation_ms}</p>
        </div>
      )}
    </section>
  );
}
