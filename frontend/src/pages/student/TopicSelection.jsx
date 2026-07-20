import { useEffect, useState } from "react";

import { api } from "../../api";
import ProgressBar from "../../components/ProgressBar";
import StatusBadge from "../../components/StatusBadge";

export default function TopicSelection({ onPractice }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.progress().then(setData).catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p>Loading topics...</p>;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Topic Selection</p>
        <h2>Kandungan Buku Teks Tahun 5</h2>
      </div>
      {data.chapters.map((chapter) => (
        <div className="card" key={chapter.id}>
          <h3>{chapter.number}. {chapter.title_ms}</h3>
          <div className="card-grid">
            {chapter.subtopics.map((subtopic) => (
              <button className="topic-card" key={subtopic.id} onClick={() => onPractice(subtopic.id)}>
                <strong>{subtopic.title_ms}</strong>
                <ProgressBar value={subtopic.score} tone={subtopic.risk_level} />
                <span>{Math.round(subtopic.score)}%</span>
                <StatusBadge status={subtopic.risk_level} />
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
