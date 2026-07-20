import { useEffect, useMemo, useState } from "react";

import { api } from "../../api";
import ProgressBar from "../../components/ProgressBar";
import StatusBadge from "../../components/StatusBadge";

export default function KnowledgeMap() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .knowledgeMap()
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  const attempted = useMemo(
    () => (data?.knowledge_map || []).filter((item) => item.attempt_count > 0),
    [data],
  );

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p>Memuatkan peta pengetahuan...</p>;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Peta Pengetahuan</p>
        <h2>Analisis Penguasaan Subtopik</h2>
      </div>

      <div className="metric-grid">
        <article className="metric-card">
          <span>Jumlah Subtopik</span>
          <strong>{data.summary.total_subtopics}</strong>
        </article>
        <article className="metric-card success">
          <span>Telah Dicuba</span>
          <strong>{data.summary.attempted_count}</strong>
        </article>
        <article className="metric-card">
          <span>Dikuasai</span>
          <strong>{data.summary.mastered_count}</strong>
        </article>
        <article className="metric-card warning">
          <span>Purata Penguasaan</span>
          <strong>{Math.round((data.summary.average_mastery || 0) * 100)}%</strong>
        </article>
      </div>

      <div className="card">
        <div className="section-header">
          <h3>Keutamaan Latihan</h3>
          <span>{attempted.length} subtopik pernah dicuba</span>
        </div>
        <div className="list-stack">
          {(data.knowledge_map || []).map((item) => (
            <article key={item.subtopic_id} className="topic-card">
              <div className="section-header">
                <div>
                  <strong>{item.subtopic_title_ms}</strong>
                  <div>{item.attempt_count} percubaan</div>
                </div>
                <StatusBadge status={item.status} />
              </div>
              <ProgressBar
                value={Math.round(item.mastery_probability * 100)}
                max={100}
                tone={item.status === "struggling" ? "danger" : item.status === "developing" ? "warning" : "success"}
                label={`${Math.round(item.mastery_probability * 100)}%`}
              />
              <div className="section-header">
                <span>{item.status_ms}</span>
                <span>Keyakinan {Math.round(item.confidence * 100)}%</span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
