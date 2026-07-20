import { useEffect, useState } from "react";

import { api } from "../../api";
import MetricCard from "../../components/MetricCard";
import ProgressBar from "../../components/ProgressBar";

export default function ProgressStats() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.progress().then(setData).catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p>Loading progress...</p>;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Progress & Stats</p>
        <h2>Kemajuan Saya</h2>
      </div>
      <div className="metric-grid">
        <MetricCard label="Average Mastery" value={`${Math.round(data.summary.average_mastery || 0)}%`} />
        <MetricCard label="Accuracy" value={`${Math.round(data.summary.accuracy || 0)}%`} tone="success" />
        <MetricCard label="Attempts" value={data.summary.attempt_count} tone="warning" />
      </div>
      {data.chapters.map((chapter) => (
        <div className="card" key={chapter.id}>
          <h3>{chapter.number}. {chapter.title_ms}</h3>
          <div className="list-stack">
            {chapter.subtopics.map((subtopic) => (
              <div className="bar-row" key={subtopic.id}>
                <span>{subtopic.title_ms}</span>
                <ProgressBar value={subtopic.score} tone={subtopic.risk_level} />
                <strong>{Math.round(subtopic.score)}%</strong>
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
