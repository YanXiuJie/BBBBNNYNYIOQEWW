import { useEffect, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";

const emptyForm = { username: "", password: "password123", full_name: "", parent_email: "", class_id: "" };

export default function StudentManagement({ onOpenStudent }) {
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [search, setSearch] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [sortBy, setSortBy] = useState("full_name");
  const [sortDir, setSortDir] = useState("asc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [error, setError] = useState("");

  async function load() {
    const [studentBody, classBody] = await Promise.all([api.students(), api.classes()]);
    const activeClasses = classBody.classes.filter((item) => item.is_active);
    setStudents(studentBody.students);
    setClasses(activeClasses);
    setForm((current) => {
      if (editingId) return current;
      if (activeClasses.some((item) => item.id === Number(current.class_id))) return current;
      return { ...current, class_id: activeClasses[0]?.id ?? "" };
    });
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      if (editingId) await api.updateStudent(editingId, form);
      else await api.createStudent(form);
      setEditingId(null);
      setForm({ ...emptyForm, class_id: classes[0]?.id ?? "" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  const filtered = students.filter((student) => {
    const matchesSearch = student.full_name.toLowerCase().includes(search.toLowerCase())
      || student.username.toLowerCase().includes(search.toLowerCase());
    const matchesClass = classFilter === "all" || String(student.class_id) === String(classFilter);
    const matchesRisk = riskFilter === "all" || student.risk_level === riskFilter;
    return matchesSearch && matchesClass && matchesRisk;
  });
  const classNameById = Object.fromEntries(classes.map((item) => [item.id, item.name]));
  const sortedStudents = [...filtered].sort((left, right) => {
    const leftValue = sortBy === "class_id" ? classNameById[left.class_id] || "" : left[sortBy];
    const rightValue = sortBy === "class_id" ? classNameById[right.class_id] || "" : right[sortBy];
    const result = typeof leftValue === "number"
      ? leftValue - rightValue
      : String(leftValue || "").localeCompare(String(rightValue || ""));
    return sortDir === "desc" ? -result : result;
  });
  const totalPages = Math.max(1, Math.ceil(sortedStudents.length / pageSize));
  const pagedStudents = sortedStudents.slice((page - 1) * pageSize, page * pageSize);

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Student Management</p>
        <h2>Student Management</h2>
        <p>Add students, assign classes, filter risk levels and open detailed analytics.</p>
      </div>
      {error && <p className="error-text">{error}</p>}
      <form className="card form-grid" onSubmit={submit}>
        <label>
          Username
          <input className="input" placeholder="nora" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} />
          <small className="form-help">Student uses this username to log in.</small>
        </label>
        <label>
          Login password
          <input className="input" placeholder="password123" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
          <small className="form-help">Student logs in with the username and this password.</small>
        </label>
        <label>
          Full name
          <input className="input" placeholder="Nora Aina" value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} />
        </label>
        <label>
          Parent email
          <input className="input" placeholder="parent@example.com" value={form.parent_email || ""} onChange={(event) => setForm({ ...form, parent_email: event.target.value })} />
        </label>
        <label>
          Class
          <select className="select" value={form.class_id} onChange={(event) => setForm({ ...form, class_id: Number(event.target.value) })}>
            {classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <div className="button-row">
          <button className="primary-button" disabled={!form.class_id}>{editingId ? "Update Student" : "Add Student"}</button>
          {editingId && (
            <button type="button" className="secondary-button" onClick={() => { setEditingId(null); setForm({ ...emptyForm, class_id: classes[0]?.id ?? "" }); }}>
              Cancel
            </button>
          )}
        </div>
      </form>
      <div className="toolbar-card">
        <input className="input" placeholder="Search student..." value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} />
        <select className="select" value={classFilter} onChange={(event) => { setClassFilter(event.target.value); setPage(1); }}>
          <option value="all">All classes</option>
          {classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <select className="select" value={riskFilter} onChange={(event) => { setRiskFilter(event.target.value); setPage(1); }}>
          <option value="all">All risk levels</option>
          <option value="high">High risk</option>
          <option value="moderate">Moderate</option>
          <option value="strong">Strong</option>
        </select>
        <select className="select" value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }}>
          <option value="full_name">Sort by name</option>
          <option value="username">Sort by username</option>
          <option value="class_id">Sort by class</option>
          <option value="mastery_average">Sort by mastery</option>
          <option value="risk_level">Sort by risk</option>
        </select>
        <select className="select" value={sortDir} onChange={(event) => { setSortDir(event.target.value); setPage(1); }}>
          <option value="asc">Ascending</option>
          <option value="desc">Descending</option>
        </select>
        <select className="select" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>
          <option value={10}>10 per page</option>
          <option value={20}>20 per page</option>
          <option value={50}>50 per page</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Name</th><th>Username</th><th>Class</th><th>Mastery</th><th>Risk</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {pagedStudents.map((student) => (
              <tr key={student.id}>
                <td>{student.full_name}</td>
                <td>{student.username}</td>
                <td>{classNameById[student.class_id] || "-"}</td>
                <td>{Math.round(student.mastery_average)}%</td>
                <td><StatusBadge status={student.risk_level} /></td>
                <td>{student.is_active ? "Active" : "Inactive"}</td>
                <td>
                  <button className="secondary-button compact" onClick={() => onOpenStudent(student.id)}>Analytics</button>
                  <button className="secondary-button compact" onClick={() => { setEditingId(student.id); setForm({ username: student.username, password: "password123", full_name: student.full_name, parent_email: student.parent_email || "", class_id: student.class_id || classes[0]?.id || "" }); }}>Edit</button>
                  <button className="danger-button compact" onClick={() => api.deleteStudent(student.id).then(load)}>Deactivate</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination-bar">
        <span>Page {page} of {totalPages} · {filtered.length} students</span>
        <div className="button-row">
          <button className="secondary-button compact" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
          <button className="secondary-button compact" disabled={page >= totalPages} onClick={() => setPage((value) => value + 1)}>Next</button>
        </div>
      </div>
    </section>
  );
}
