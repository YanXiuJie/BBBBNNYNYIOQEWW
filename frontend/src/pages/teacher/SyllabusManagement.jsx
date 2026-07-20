import { useEffect, useState } from "react";

import { api } from "../../api";

export default function SyllabusManagement() {
  const [chapters, setChapters] = useState([]);
  const [chapterForm, setChapterForm] = useState({ number: 9, title_ms: "" });
  const [editingChapterId, setEditingChapterId] = useState(null);
  const [subtopicForm, setSubtopicForm] = useState({ chapter_id: 1, title_ms: "", activity_type: "lesson" });
  const [editingSubtopicId, setEditingSubtopicId] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    const body = await api.syllabus();
    setChapters(body.chapters);
    setSubtopicForm((current) => ({ ...current, chapter_id: body.chapters[0]?.id || 1 }));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  async function saveChapter(event) {
    event.preventDefault();
    setError("");
    try {
      if (editingChapterId) await api.updateChapter(editingChapterId, chapterForm);
      else await api.createChapter(chapterForm);
      setEditingChapterId(null);
      setChapterForm({ number: 9, title_ms: "" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function saveSubtopic(event) {
    event.preventDefault();
    setError("");
    try {
      if (editingSubtopicId) await api.updateSubtopic(editingSubtopicId, subtopicForm);
      else await api.createSubtopic(subtopicForm);
      setEditingSubtopicId(null);
      setSubtopicForm({ chapter_id: chapters[0]?.id || 1, title_ms: "", activity_type: "lesson" });
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Syllabus</p>
        <h2>Syllabus Management</h2>
        <p>Manage textbook chapters and subtopics used by adaptive practice and question generation.</p>
      </div>
      {error && <p className="error-text">{error}</p>}
      <div className="two-column">
        <form className="card form-grid" onSubmit={saveChapter}>
          <h3>{editingChapterId ? "Edit Chapter" : "Add Chapter"}</h3>
          <label>
            Number
            <input className="input" type="number" value={chapterForm.number} onChange={(event) => setChapterForm({ ...chapterForm, number: Number(event.target.value) })} />
          </label>
          <label>
            Chapter title
            <input className="input" placeholder="Latihan Tambahan" value={chapterForm.title_ms} onChange={(event) => setChapterForm({ ...chapterForm, title_ms: event.target.value })} />
          </label>
          <div className="button-row">
            <button className="primary-button">{editingChapterId ? "Update Chapter" : "Add Chapter"}</button>
            {editingChapterId && (
              <button type="button" className="secondary-button" onClick={() => { setEditingChapterId(null); setChapterForm({ number: 9, title_ms: "" }); }}>Cancel</button>
            )}
          </div>
        </form>
        <form className="card form-grid" onSubmit={saveSubtopic}>
          <h3>{editingSubtopicId ? "Edit Subtopic" : "Add Subtopic"}</h3>
          <label>
            Chapter
            <select className="select" value={subtopicForm.chapter_id} onChange={(event) => setSubtopicForm({ ...subtopicForm, chapter_id: Number(event.target.value) })}>
              {chapters.map((chapter) => <option key={chapter.id} value={chapter.id}>{chapter.number}. {chapter.title_ms}</option>)}
            </select>
          </label>
          <label>
            Subtopic title
            <input className="input" placeholder="Latihan Campuran" value={subtopicForm.title_ms} onChange={(event) => setSubtopicForm({ ...subtopicForm, title_ms: event.target.value })} />
          </label>
          <label>
            Activity type
            <select className="select" value={subtopicForm.activity_type} onChange={(event) => setSubtopicForm({ ...subtopicForm, activity_type: event.target.value })}>
              <option value="lesson">Lesson</option>
              <option value="practice">Practice</option>
              <option value="diagnostic">Diagnostic</option>
              <option value="revision">Revision</option>
            </select>
          </label>
          <div className="button-row">
            <button className="primary-button">{editingSubtopicId ? "Update Subtopic" : "Add Subtopic"}</button>
            {editingSubtopicId && (
              <button type="button" className="secondary-button" onClick={() => { setEditingSubtopicId(null); setSubtopicForm({ chapter_id: chapters[0]?.id || 1, title_ms: "", activity_type: "lesson" }); }}>Cancel</button>
            )}
          </div>
        </form>
      </div>
      {chapters.map((chapter) => (
        <div className="card" key={chapter.id}>
          <div className="section-header">
            <h3>{chapter.number}. {chapter.title_ms}</h3>
            <div className="button-row">
              <button className="secondary-button compact" onClick={() => { setEditingChapterId(chapter.id); setChapterForm({ number: chapter.number, title_ms: chapter.title_ms }); }}>Edit</button>
              <button className="danger-button compact" onClick={() => api.deleteChapter(chapter.id).then(load)}>Deactivate</button>
            </div>
          </div>
          <div className="card-grid">
            {chapter.subtopics.map((subtopic) => (
              <div className="topic-card" key={subtopic.id}>
                <strong>{subtopic.title_ms}</strong>
                <span>{subtopic.activity_type}</span>
                <div className="button-row">
                  <button className="secondary-button compact" onClick={() => {
                    setEditingSubtopicId(subtopic.id);
                    setSubtopicForm({ chapter_id: subtopic.chapter_id, title_ms: subtopic.title_ms, activity_type: subtopic.activity_type });
                  }}>Edit</button>
                  <button className="danger-button compact" onClick={() => api.deleteSubtopic(subtopic.id).then(load)}>Deactivate</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
