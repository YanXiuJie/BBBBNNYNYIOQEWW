import { useEffect, useState } from "react";

import { api } from "../../api";
import MetricCard from "../../components/MetricCard";
import StatusBadge from "../../components/StatusBadge";

export default function StudentDashboard({ onPractice, onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.studentDashboard().then(setData).catch((err) => setError(err.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p>Loading dashboard...</p>;

  const needsDiagnostic = !data.diagnostic_completed;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Student Dashboard</p>
        <h2>Selamat datang, {data.student.full_name}</h2>
      </div>
      <div className="metric-grid">
        <MetricCard label="Diagnostic" value={data.diagnostic_completed ? "Completed" : "Not Started"} />
        <MetricCard label="Weak Subtopics" value={needsDiagnostic ? "After test" : data.weak_subtopics.length} tone="warning" />
        <MetricCard label="Recommendation" value={needsDiagnostic ? "Diagnostic Test" : data.recommended_subtopic?.title_ms || "Ready"} tone="primary" />
      </div>
      <div className="card highlight-card">
        <div>
          <p className="eyebrow">AI Recommended Next Activity</p>
          <h3>{needsDiagnostic ? "Mulakan Ujian Diagnostik" : data.recommended_subtopic?.title_ms || "Mulakan latihan"}</h3>
          <p>
            {needsDiagnostic
              ? "Ujian diagnostik menetapkan mastery awal sebelum latihan adaptif bermula."
              : "Latihan seterusnya dipilih berdasarkan mastery, jawapan dan masa menjawab."}
          </p>
        </div>
        <button
          className="primary-button"
          onClick={() => (needsDiagnostic ? onNavigate("diagnostic") : onPractice(data.recommended_subtopic?.id || 10))}
        >
          {needsDiagnostic ? "Mula Diagnostik" : "Mula Latihan"}
        </button>
      </div>
      <div className="card">
        <div className="section-header">
          <h3>Latihan Menyeluruh</h3>
        </div>
        <p>Cuba latihan menyeluruh yang merangkumi semua topik dengan 3 tahap kesukaran.</p>
        <button className="secondary-button" onClick={() => onNavigate("comprehensive")}>
          Mulakan Latihan Menyeluruh
        </button>
      </div>
      <div className="card">
        <div className="section-header">
          <h3>Topik Perlu Perhatian</h3>
          <button className="secondary-button" onClick={() => onNavigate("progress")}>Lihat Kemajuan</button>
        </div>
        <div className="card-grid">
          {needsDiagnostic ? (
            <p>Selesaikan ujian diagnostik dahulu untuk mengenal pasti topik lemah.</p>
          ) : data.weak_subtopics.length ? data.weak_subtopics.map((item) => (
            <button className="topic-card" key={item.id} onClick={() => onPractice(item.id)}>
              <strong>{item.title_ms}</strong>
              <StatusBadge status={item.risk_level} />
            </button>
          )) : <p>Tiada topik lemah direkodkan.</p>}
        </div>
      </div>
    </section>
  );
}
