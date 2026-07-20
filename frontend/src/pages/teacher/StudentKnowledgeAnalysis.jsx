import { useEffect, useState } from "react";

import { api } from "../../api";
import ProgressBar from "../../components/ProgressBar";
import StatusBadge from "../../components/StatusBadge";

export default function StudentKnowledgeAnalysis({ studentId }) {
  const [syllabus, setSyllabus] = useState([]);
  const [subtopicId, setSubtopicId] = useState(null);
  const [difficulty, setDifficulty] = useState("medium");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .syllabus()
      .then((body) => {
        setSyllabus(body.chapters);
        const firstSubtopic = body.chapters.flatMap((chapter) => chapter.subtopics || [])[0];
        if (firstSubtopic) {
          setSubtopicId(firstSubtopic.id);
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!studentId || !subtopicId) return;
    api
      .studentKnowledgePrediction(studentId, subtopicId, difficulty)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [studentId, subtopicId, difficulty]);

  const subtopics = syllabus.flatMap((chapter) =>
    (chapter.subtopics || []).map((subtopic) => ({
      ...subtopic,
      chapter_title_ms: chapter.title_ms,
    })),
  );

  if (!studentId) return <p>Pilih murid dahulu.</p>;
  if (error) return <p className="error-text">{error}</p>;
  if (!subtopicId || !data) return <p>Memuatkan analisis pengetahuan...</p>;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Knowledge Analysis</p>
        <h2>{data.student.full_name}</h2>
      </div>

      <div className="card form-grid">
        <label>
          Subtopik
          <select className="select" value={subtopicId} onChange={(event) => setSubtopicId(Number(event.target.value))}>
            {subtopics.map((subtopic) => (
              <option key={subtopic.id} value={subtopic.id}>
                {subtopic.chapter_title_ms} - {subtopic.title_ms}
              </option>
            ))}
          </select>
        </label>
        <label>
          Kesukaran
          <select className="select" value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
            <option value="easy">Mudah</option>
            <option value="medium">Sederhana</option>
            <option value="hard">Sukar</option>
          </select>
        </label>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span>Kebarangkalian Penguasaan</span>
          <strong>{Math.round(data.current_state.mastery_probability * 100)}%</strong>
        </article>
        <article className="metric-card warning">
          <span>Keyakinan</span>
          <strong>{Math.round(data.current_state.confidence * 100)}%</strong>
        </article>
        <article className="metric-card">
          <span>Percubaan</span>
          <strong>{data.current_state.attempt_count}</strong>
        </article>
      </div>

      <div className="card">
        <h3>Ramalan Prestasi</h3>
        <div className="list-stack">
          {["easy", "medium", "hard"].map((level) => (
            <article key={level} className="topic-card">
              <div className="section-header">
                <strong>{level === "easy" ? "Mudah" : level === "medium" ? "Sederhana" : "Sukar"}</strong>
                <StatusBadge status={level} />
              </div>
              <ProgressBar value={Math.round(data.predictions[level] * 100)} max={100} label={`${Math.round(data.predictions[level] * 100)}%`} />
            </article>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Cadangan</h3>
        <p>{data.recommendation_ms}</p>
      </div>
    </section>
  );
}
