import { useEffect, useState } from "react";

import { api } from "../../api";
import MetricCard from "../../components/MetricCard";
import ProgressBar from "../../components/ProgressBar";
import { formatDateTime } from "../../utils";

export default function StudentDetail({ studentId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!studentId) {
      setData(null);
      setError("");
      return;
    }
    api.studentAnalytics(studentId).then(setData).catch((err) => setError(err.message));
  }, [studentId]);

  if (error) return <p className="error-text">{error}</p>;
  if (!studentId) {
    return (
      <section className="page-stack">
        <div className="page-title">
          <p className="eyebrow">Student Detail Analytics</p>
          <h2>Select a student</h2>
        </div>
        <div className="card">
          <p>Open a student from Class Dashboard or Student Management to view detailed analytics.</p>
        </div>
      </section>
    );
  }
  if (!data) return <p>Loading student analytics...</p>;

  const summary = data.progress.summary;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Student Detail Analytics</p>
        <h2>{data.student.full_name}</h2>
      </div>
      <div className="metric-grid">
        <MetricCard label="Average Mastery" value={`${Math.round(summary.average_mastery || 0)}%`} />
        <MetricCard label="Accuracy" value={`${Math.round(summary.accuracy || 0)}%`} tone="success" />
        <MetricCard label="Attempts" value={summary.attempt_count} tone="warning" />
      </div>
      <div className="card">
        <h3>Recommended Path</h3>
        <div className="card-grid">
          {data.recommended_path.map((item) => (
            <div className="topic-card" key={item.id}>
              <strong>{item.title_ms}</strong>
              <ProgressBar value={item.score} tone={item.risk_level} />
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <h3>Recent Attempts</h3>
        <div className="list-stack">
          {data.recent_attempts.map((attempt) => (
            <p key={attempt.id}>
              {formatDateTime(attempt.created_at)} · {attempt.question?.subtopic?.title_ms}: {attempt.is_correct ? "Correct" : "Wrong"} ({attempt.answer_text}, {attempt.time_seconds}s)
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}
