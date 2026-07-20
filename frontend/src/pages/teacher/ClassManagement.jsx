import { useEffect, useState } from "react";

import { api } from "../../api";

const emptyForm = { name: "", year_level: 5, section: "A" };

export default function ClassManagement() {
  const [classes, setClasses] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [statusFilter, setStatusFilter] = useState("active");
  const [error, setError] = useState("");

  async function load() {
    setClasses((await api.classes()).classes);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      if (editingId) await api.updateClass(editingId, form);
      else await api.createClass(form);
      setForm(emptyForm);
      setEditingId(null);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Class Management</p>
        <h2>Class Management</h2>
        <p>Manage student groups used for assignment, filtering and class analytics.</p>
      </div>
      {error && <p className="error-text">{error}</p>}
      <form className="card form-grid" onSubmit={submit}>
        <label>
          Class name
          <input className="input" placeholder="Tahun 5 Bestari" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
          <small className="form-help">Display name shown in dashboards and student assignment.</small>
        </label>
        <label>
          Year level
          <input className="input" type="number" min="1" value={form.year_level} onChange={(event) => setForm({ ...form, year_level: Number(event.target.value) })} />
          <small className="form-help">School grade level. For this system, this is normally 5.</small>
        </label>
        <label>
          Section
          <input className="input" placeholder="A" value={form.section} onChange={(event) => setForm({ ...form, section: event.target.value })} />
          <small className="form-help">Class section or group label, such as A, B or Bestari.</small>
        </label>
        <div className="button-row">
          <button className="primary-button">{editingId ? "Update Class" : "Add Class"}</button>
          {editingId && (
            <button type="button" className="secondary-button" onClick={() => { setEditingId(null); setForm(emptyForm); }}>
              Cancel
            </button>
          )}
        </div>
      </form>
      <div className="toolbar-card">
        <button className={statusFilter === "active" ? "filter-chip active" : "filter-chip"} onClick={() => setStatusFilter("active")}>Active</button>
        <button className={statusFilter === "all" ? "filter-chip active" : "filter-chip"} onClick={() => setStatusFilter("all")}>All</button>
        <button className={statusFilter === "inactive" ? "filter-chip active" : "filter-chip"} onClick={() => setStatusFilter("inactive")}>Inactive</button>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Name</th><th>Year</th><th>Section</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {classes.filter((item) => statusFilter === "all" || (statusFilter === "active" ? item.is_active : !item.is_active)).map((item) => (
              <tr key={item.id}>
                <td>{item.name}</td>
                <td>{item.year_level}</td>
                <td>{item.section}</td>
                <td>{item.is_active ? "Active" : "Inactive"}</td>
                <td>
                  <button className="secondary-button compact" onClick={() => { setEditingId(item.id); setForm({ name: item.name, year_level: item.year_level, section: item.section }); }}>Edit</button>
                  <button className="danger-button compact" onClick={() => api.deleteClass(item.id).then(load)}>Deactivate</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
