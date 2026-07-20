import { useEffect, useState } from "react";

import { api } from "../../api";
import { formatDateTime } from "../../utils";

export default function ReviewMistakes({ onPractice }) {
  const [mistakes, setMistakes] = useState([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [pagination, setPagination] = useState({ page: 1, page_size: 10, total: 0, total_pages: 1 });
  const [error, setError] = useState("");

  useEffect(() => {
    api.mistakes({ page, page_size: pageSize, sort_by: sortBy, sort_dir: sortDir })
      .then((body) => {
        setMistakes(body.mistakes);
        setPagination(body.pagination || { page, page_size: pageSize, total: body.mistakes.length, total_pages: 1 });
      })
      .catch((err) => setError(err.message));
  }, [page, pageSize, sortBy, sortDir]);

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Review Mistakes</p>
        <h2>Ulang Kaji Kesalahan</h2>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="toolbar-card">
        <select className="select" value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }}>
          <option value="created_at">Sort by answered time</option>
          <option value="time_seconds">Sort by time spent</option>
          <option value="subtopic_id">Sort by subtopic</option>
        </select>
        <select className="select" value={sortDir} onChange={(event) => { setSortDir(event.target.value); setPage(1); }}>
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
        <select className="select" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>
          <option value={5}>5 per page</option>
          <option value={10}>10 per page</option>
          <option value={20}>20 per page</option>
        </select>
      </div>
      {mistakes.length ? mistakes.map((item) => (
        <div className="card" key={item.id}>
          <p className="eyebrow">{item.question?.subtopic?.title_ms}</p>
          <h3>{item.question?.prompt_ms}</h3>
          <p>Answered: <strong>{formatDateTime(item.created_at)}</strong></p>
          <p>Masa: <strong>{item.time_seconds}s</strong></p>
          <p>Jawapan saya: <strong>{item.answer_text}</strong></p>
          <p>Jawapan betul: <strong>{item.question?.expected_answer}</strong></p>
          <p>{item.feedback_ms}</p>
          <button className="secondary-button" onClick={() => onPractice(item.question?.subtopic_id || 10)}>
            Cuba Soalan Serupa
          </button>
        </div>
      )) : <div className="card"><p>Tiada kesalahan direkodkan.</p></div>}
      <div className="pagination-bar">
        <span>Page {pagination.page} of {pagination.total_pages} · {pagination.total} mistakes</span>
        <div className="button-row">
          <button className="secondary-button compact" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
          <button className="secondary-button compact" disabled={page >= pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button>
        </div>
      </div>
    </section>
  );
}
