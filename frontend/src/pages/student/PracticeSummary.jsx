import { useEffect, useState } from "react";

import { api } from "../../api";

const PHASE_LABELS = {
  diagnosis: "Diagnostik",
  remedial: "Pemulihan",
  consolidation: "Pengukuhan",
};

export default function PracticeSummary({ sessionId, onRestart }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sessionId) return;
    api.getComprehensiveSummary(sessionId).then(setData).catch((err) => setError(err.message));
  }, [sessionId]);

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p>Memuatkan ringkasan...</p>;

  const overallAccuracy = data.overall_metrics?.accuracy ?? data.summary?.accuracy ?? 0;
  const avgTime = data.overall_metrics?.avg_time_seconds ?? data.summary?.average_time_seconds ?? 0;
  const totalHints = data.overall_metrics?.total_hints_used ?? data.summary?.total_hints_used ?? 0;
  const totalQuestions = data.overall_metrics?.total_questions ?? data.summary?.total_questions ?? 0;

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Latihan Menyeluruh</p>
        <h2>Ringkasan Prestasi</h2>
      </div>

      <div className="card">
        <h3>Prestasi Keseluruhan</h3>
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-value">{Math.round(overallAccuracy)}%</div>
            <div className="metric-label">Ketepatan</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{Math.round(avgTime)}s</div>
            <div className="metric-label">Purata Masa</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{totalHints}</div>
            <div className="metric-label">Petunjuk Digunakan</div>
          </div>
          <div className="metric-card">
            <div className="metric-value">{totalQuestions}</div>
            <div className="metric-label">Jumlah Soalan</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Perbandingan Fasa</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Fasa</th>
              <th>Betul</th>
              <th>Salah</th>
              <th>Ketepatan</th>
              <th>Purata Masa</th>
              <th>Petunjuk</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.phase_breakdown || {}).map(([phase, metrics]) => (
              <tr key={phase}>
                <td><strong>{PHASE_LABELS[phase] || phase}</strong></td>
                <td className="success-text">{metrics.correct || 0}</td>
                <td className="danger-text">{metrics.incorrect || 0}</td>
                <td>{Math.round(metrics.accuracy || 0)}%</td>
                <td>{Math.round(metrics.avg_time || 0)}s</td>
                <td>{metrics.hints_used || 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.mastery_changes?.length > 0 && (
        <div className="card">
          <h3>Perubahan Penguasaan</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Topik</th>
                <th>Sebelum</th>
                <th>Selepas</th>
                <th>Perubahan</th>
              </tr>
            </thead>
            <tbody>
              {data.mastery_changes.map((change, idx) => {
                const delta = change.after - change.before;
                const deltaClass = delta > 0 ? "success-text" : delta < 0 ? "danger-text" : "";
                return (
                  <tr key={idx}>
                    <td>{change.subtopic_name}</td>
                    <td>{Math.round(change.before)}%</td>
                    <td>{Math.round(change.after)}%</td>
                    <td className={deltaClass}>
                      {delta > 0 ? "+" : ""}{Math.round(delta)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {data.weak_points?.length > 0 && (
        <div className="card danger-card">
          <h3>Kawasan Lemah</h3>
          <ul>
            {data.weak_points.map((point, idx) => (
              <li key={idx}>
                <strong>{point.subtopic_name}</strong> - Ketepatan: {Math.round(point.accuracy)}%
              </li>
            ))}
          </ul>
        </div>
      )}

      {data.next_steps && (
        <div className="card">
          <h3>Cadangan Seterusnya</h3>
          <p>{data.next_steps}</p>
        </div>
      )}

      <div className="card">
        <div className="button-group">
          <button className="primary-button" onClick={onRestart}>Mulakan Latihan Baru</button>
          <button className="secondary-button" onClick={() => window.print()}>Cetak Ringkasan</button>
        </div>
      </div>
    </section>
  );
}
