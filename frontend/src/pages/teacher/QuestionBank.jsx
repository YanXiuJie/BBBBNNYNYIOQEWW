import { useEffect, useState } from "react";

import { api } from "../../api";
import StatusBadge from "../../components/StatusBadge";
import { formatDateTime } from "../../utils";

const emptyQuestion = {
  chapter_id: null,
  subtopic_id: null,
  difficulty: "medium",
  question_type: "short_answer",
  prompt_ms: "",
  expected_answer: "",
  options: [],
  hint_ms: "",
  hint_level2_ms: "",
  hint_level3_ms: "",
  explanation_ms: "",
};

function questionTemplate(chapters) {
  const firstChapter = chapters.find((chapter) => chapter.subtopics?.length);
  return {
    ...emptyQuestion,
    chapter_id: firstChapter?.id ?? null,
    subtopic_id: firstChapter?.subtopics?.[0]?.id ?? null,
  };
}

function previewText(value, maxLength = 180) {
  const text = value || "-";
  return text.length > maxLength ? `${text.slice(0, maxLength).trim()}...` : text;
}

export default function QuestionBank() {
  const [questions, setQuestions] = useState([]);
  const [chapters, setChapters] = useState([]);
  const [form, setForm] = useState(emptyQuestion);
  const [editingId, setEditingId] = useState(null);
  const [difficultyFilter, setDifficultyFilter] = useState("all");
  const [subtopicFilter, setSubtopicFilter] = useState("all");
  const [questionTypeFilter, setQuestionTypeFilter] = useState("all");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [pagination, setPagination] = useState({ page: 1, page_size: 10, total: 0, total_pages: 1 });
  const [error, setError] = useState("");

  async function load() {
    const [questionBody, syllabusBody] = await Promise.all([
      api.questions({
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_dir: sortDir,
        difficulty: difficultyFilter,
        subtopic_id: subtopicFilter,
        question_type: questionTypeFilter,
      }),
      api.syllabus(),
    ]);
    setQuestions(questionBody.questions);
    setPagination(questionBody.pagination || { page, page_size: pageSize, total: questionBody.questions.length, total_pages: 1 });
    setChapters(syllabusBody.chapters);
    setForm((current) => current.chapter_id ? current : questionTemplate(syllabusBody.chapters));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [page, pageSize, sortBy, sortDir, difficultyFilter, subtopicFilter, questionTypeFilter]);

  const selectedChapter = chapters.find((chapter) => chapter.id === Number(form.chapter_id));
  const allSubtopics = chapters.flatMap((chapter) => chapter.subtopics);

  async function submit(event) {
    event.preventDefault();
    setError("");
    if (!form.chapter_id || !form.subtopic_id) {
      setError("Please select a chapter and subtopic.");
      return;
    }
    const payload = {
      ...form,
      options: form.question_type === "multiple_choice" ? form.options : [],
    };
    try {
      if (editingId) await api.updateQuestion(editingId, payload);
      else await api.createQuestion(payload);
      setEditingId(null);
      setForm(questionTemplate(chapters));
      setPage(1);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Question Bank</p>
        <h2>Question Bank Management</h2>
        <p>Create, edit, filter and deactivate validated questions.</p>
      </div>
      {error && <p className="error-text">{error}</p>}
      <form className="card form-grid question-form" onSubmit={submit}>
        <h3>{editingId ? "Edit Question" : "Create Manual Question"}</h3>
        <label>
          Chapter
          <select className="select" value={form.chapter_id ?? ""} onChange={(event) => {
            const chapter = chapters.find((item) => item.id === Number(event.target.value));
            setForm({ ...form, chapter_id: Number(event.target.value), subtopic_id: chapter?.subtopics?.[0]?.id || form.subtopic_id });
          }}>
            {chapters.map((chapter) => <option key={chapter.id} value={chapter.id}>{chapter.number}. {chapter.title_ms}</option>)}
          </select>
        </label>
        <label>
          Subtopic
          <select className="select" value={form.subtopic_id ?? ""} onChange={(event) => setForm({ ...form, subtopic_id: Number(event.target.value) })}>
            {(selectedChapter?.subtopics || []).map((subtopic) => <option key={subtopic.id} value={subtopic.id}>{subtopic.title_ms}</option>)}
          </select>
        </label>
        <label>
          Difficulty
          <select className="select" value={form.difficulty} onChange={(event) => setForm({ ...form, difficulty: event.target.value })}>
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </label>
        <label>
          Question type
          <select className="select" value={form.question_type} onChange={(event) => setForm({ ...form, question_type: event.target.value })}>
            <option value="short_answer">Short answer</option>
            <option value="multiple_choice">Multiple choice</option>
          </select>
        </label>
        <label className="wide-field">
          Question
          <textarea className="input" rows="3" value={form.prompt_ms} onChange={(event) => setForm({ ...form, prompt_ms: event.target.value })} />
        </label>
        <label>
          Answer
          <input className="input" value={form.expected_answer} onChange={(event) => setForm({ ...form, expected_answer: event.target.value })} />
        </label>
        <label>
          Hint 1
          <input className="input" value={form.hint_ms} onChange={(event) => setForm({ ...form, hint_ms: event.target.value })} />
        </label>
        <label>
          Hint 2
          <input className="input" value={form.hint_level2_ms} onChange={(event) => setForm({ ...form, hint_level2_ms: event.target.value })} />
        </label>
        <label>
          Hint 3
          <input className="input" value={form.hint_level3_ms} onChange={(event) => setForm({ ...form, hint_level3_ms: event.target.value })} />
        </label>
        {form.question_type === "multiple_choice" && (
          <label className="wide-field">
            Options
            <textarea
              className="input"
              rows="4"
              placeholder="One option per line. Include the correct answer."
              value={form.options.join("\n")}
              onChange={(event) => setForm({ ...form, options: event.target.value.split("\n").map((item) => item.trim()).filter(Boolean) })}
            />
          </label>
        )}
        <label className="wide-field">
          Explanation
          <textarea className="input" rows="3" value={form.explanation_ms} onChange={(event) => setForm({ ...form, explanation_ms: event.target.value })} />
        </label>
        <div className="button-row">
          <button className="primary-button">{editingId ? "Update Question" : "Create Question"}</button>
          {editingId && (
            <button type="button" className="secondary-button" onClick={() => { setEditingId(null); setForm(questionTemplate(chapters)); }}>Cancel</button>
          )}
        </div>
      </form>
      <div className="toolbar-card">
        <select className="select" value={subtopicFilter} onChange={(event) => { setSubtopicFilter(event.target.value); setPage(1); }}>
          <option value="all">All subtopics</option>
          {allSubtopics.map((subtopic) => <option key={subtopic.id} value={subtopic.id}>{subtopic.title_ms}</option>)}
        </select>
        <select className="select" value={difficultyFilter} onChange={(event) => { setDifficultyFilter(event.target.value); setPage(1); }}>
          <option value="all">All difficulties</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <select className="select" value={questionTypeFilter} onChange={(event) => { setQuestionTypeFilter(event.target.value); setPage(1); }}>
          <option value="all">All types</option>
          <option value="short_answer">Short answer</option>
          <option value="multiple_choice">Multiple choice</option>
        </select>
        <select className="select" value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(1); }}>
          <option value="created_at">Sort by created</option>
          <option value="difficulty">Sort by difficulty</option>
          <option value="subtopic_id">Sort by subtopic</option>
          <option value="source">Sort by source</option>
          <option value="question_type">Sort by type</option>
        </select>
        <select className="select" value={sortDir} onChange={(event) => { setSortDir(event.target.value); setPage(1); }}>
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>
        <select className="select" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPage(1); }}>
          <option value={10}>10 per page</option>
          <option value={20}>20 per page</option>
          <option value={50}>50 per page</option>
        </select>
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead><tr><th>Created</th><th>Subtopic</th><th>Question</th><th>Answer</th><th>Hints</th><th>Explanation</th><th>Type</th><th>Options</th><th>Difficulty</th><th>Source</th><th>Action</th></tr></thead>
          <tbody>
            {questions.map((question) => (
              <tr key={question.id}>
                <td>{formatDateTime(question.created_at)}</td>
                <td>{question.subtopic?.title_ms}</td>
                <td>{question.prompt_ms}</td>
                <td>{question.expected_answer}</td>
                <td>
                  <div><strong>1:</strong> {question.hint_ms || "-"}</div>
                  <div><strong>2:</strong> {question.hint_level2_ms || "-"}</div>
                  <div><strong>3:</strong> {question.hint_level3_ms || "-"}</div>
                </td>
                <td title={question.explanation_ms}>{previewText(question.explanation_ms)}</td>
                <td><StatusBadge status={question.question_type} /></td>
                <td>{question.options?.length ? question.options.join(", ") : "-"}</td>
                <td><StatusBadge status={question.difficulty} /></td>
                <td><StatusBadge status={question.source} /></td>
                <td>
                  <button className="secondary-button compact" onClick={() => {
                    setEditingId(question.id);
                    setForm({
                      chapter_id: question.chapter_id,
                      subtopic_id: question.subtopic_id,
                      difficulty: question.difficulty,
                      question_type: question.question_type || "short_answer",
                      prompt_ms: question.prompt_ms,
                      expected_answer: question.expected_answer,
                      options: question.options || [],
                      hint_ms: question.hint_ms,
                      hint_level2_ms: question.hint_level2_ms || "",
                      hint_level3_ms: question.hint_level3_ms || "",
                      explanation_ms: question.explanation_ms,
                    });
                  }}>Edit</button>
                  <button className="danger-button compact" onClick={() => api.deleteQuestion(question.id).then(load)}>Disable</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="pagination-bar">
        <span>Page {pagination.page} of {pagination.total_pages} · {pagination.total} questions</span>
        <div className="button-row">
          <button className="secondary-button compact" disabled={page <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</button>
          <button className="secondary-button compact" disabled={page >= pagination.total_pages} onClick={() => setPage((value) => value + 1)}>Next</button>
        </div>
      </div>
    </section>
  );
}
