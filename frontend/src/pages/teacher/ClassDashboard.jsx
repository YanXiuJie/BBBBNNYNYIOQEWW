import { useEffect, useState } from "react";

import { api } from "../../api";
import MetricCard from "../../components/MetricCard";
import ProgressBar from "../../components/ProgressBar";
import StatusBadge from "../../components/StatusBadge";

export default function ClassDashboard({ onOpenStudent }) {
  const [classes, setClasses] = useState([]);
  const [classId, setClassId] = useState(1);
  const [analytics, setAnalytics] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.classes().then((body) => {
      setClasses(body.classes);
      setClassId(body.classes[0]?.id || 1);
    }).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    api.classAnalytics(classId).then(setAnalytics).catch((err) => setError(err.message));
  }, [classId]);

  return (
    <section className="page-stack">
      <div className="section-header">
        <div className="page-title">
          <p className="eyebrow">Class Analytics</p>
          <h2>Class Dashboard</h2>
        </div>
        <select className="select" value={classId} onChange={(event) => setClassId(Number(event.target.value))}>
          {classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </div>
      {error && <p className="error-text">{error}</p>}
      {analytics && (
        <>
          <div className="metric-grid">
            <MetricCard label="Average Mastery" value={`${Math.round(analytics.summary.average_mastery || 0)}%`} />
            <MetricCard label="Average Accuracy" value={`${Math.round(analytics.summary.average_accuracy || 0)}%`} tone="success" />
            <MetricCard label="At Risk" value={analytics.summary.at_risk_count} tone="danger" />
            <MetricCard label="Students" value={analytics.summary.student_count} tone="warning" />
          </div>
          <div className="card">
            <h3>Weak Subtopics</h3>
            <div className="list-stack">
              {analytics.weak_subtopics.length ? analytics.weak_subtopics.map((item) => (
                <div className="bar-row" key={item.subtopic_id}>
                  <span>{item.title_ms}</span>
                  <ProgressBar value={item.average_mastery} tone="danger" />
                  <strong>{Math.round(item.average_mastery)}%</strong>
                </div>
              )) : <p>No weak subtopics yet.</p>}
            </div>
          </div>
          <div className="card">
            <h3>Student Risk List</h3>
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Name</th><th>Mastery</th><th>Accuracy</th><th>Risk</th><th>Action</th></tr></thead>
                <tbody>
                  {analytics.students.map((student) => (
                    <tr key={student.id}>
                      <td>{student.full_name}</td>
                      <td>{Math.round(student.mastery_average)}%</td>
                      <td>{Math.round(student.accuracy)}%</td>
                      <td><StatusBadge status={student.risk_level} /></td>
                      <td><button className="secondary-button compact" onClick={() => onOpenStudent(student.id)}>Analytics</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
