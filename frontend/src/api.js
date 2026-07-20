const API_BASE = "http://127.0.0.1:8000";

function token() {
  return localStorage.getItem("token");
}

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const authToken = token();
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  // 401 时立即清理并跳转
  if (response.status === 401) {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/";  // 强制跳转到登录页
    throw new Error("Session expired. Please login again.");
  }

  // 解析响应体
  let body;
  try {
    body = await response.json();
  } catch {
    body = { detail: response.statusText || "Unknown error" };
  }

  if (!response.ok) {
    throw new Error(body.detail || `Request failed with status ${response.status}`);
  }

  return body;
}

function queryString(params = {}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "" && value !== "all") {
      search.set(key, value);
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const api = {
  login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  syllabus: () => request("/syllabus"),
  studentDashboard: () => request("/student/dashboard"),
  startDiagnostic: () => request("/student/diagnostic/start", { method: "POST" }),
  nextDiagnosticQuestion: (sessionId) => request(`/student/diagnostic/next?session_id=${sessionId}`),
  submitDiagnosticAnswer: (payload) => request("/student/diagnostic/submit", { method: "POST", body: JSON.stringify(payload) }),
  diagnosticSummary: (sessionId) => request(`/student/diagnostic/summary?session_id=${sessionId}`),
  nextQuestion: (subtopicId) => request(`/student/next-question?subtopic_id=${subtopicId}`),
  submitAttempt: (payload) => request("/student/attempts", { method: "POST", body: JSON.stringify(payload) }),
  progress: () => request("/student/progress"),
  mistakes: (params) => request(`/student/mistakes${queryString(params)}`),
  classes: () => request("/teacher/classes"),
  createClass: (payload) => request("/teacher/classes", { method: "POST", body: JSON.stringify(payload) }),
  updateClass: (id, payload) => request(`/teacher/classes/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteClass: (id) => request(`/teacher/classes/${id}`, { method: "DELETE" }),
  chapters: () => request("/teacher/chapters"),
  createChapter: (payload) => request("/teacher/chapters", { method: "POST", body: JSON.stringify(payload) }),
  updateChapter: (id, payload) => request(`/teacher/chapters/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteChapter: (id) => request(`/teacher/chapters/${id}`, { method: "DELETE" }),
  createSubtopic: (payload) => request("/teacher/subtopics", { method: "POST", body: JSON.stringify(payload) }),
  updateSubtopic: (id, payload) => request(`/teacher/subtopics/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteSubtopic: (id) => request(`/teacher/subtopics/${id}`, { method: "DELETE" }),
  students: () => request("/teacher/students"),
  createStudent: (payload) => request("/teacher/students", { method: "POST", body: JSON.stringify(payload) }),
  updateStudent: (id, payload) => request(`/teacher/students/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteStudent: (id) => request(`/teacher/students/${id}`, { method: "DELETE" }),
  classAnalytics: (classId) => request(`/teacher/analytics/classes/${classId}`),
  studentAnalytics: (studentId) => request(`/teacher/analytics/students/${studentId}`),
  knowledgeMap: (chapterId) => request(`/student/knowledge-map${chapterId ? `?chapter_id=${chapterId}` : ""}`),
  studentKnowledgePrediction: (studentId, subtopicId, difficulty = "medium") =>
    request(`/teacher/students/${studentId}/knowledge-prediction?subtopic_id=${subtopicId}&difficulty=${difficulty}`),
  questions: (params) => request(`/teacher/questions${queryString(params)}`),
  createQuestion: (payload) => request("/teacher/questions", { method: "POST", body: JSON.stringify(payload) }),
  updateQuestion: (id, payload) => request(`/teacher/questions/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteQuestion: (id) => request(`/teacher/questions/${id}`, { method: "DELETE" }),
  generateQuestion: (payload) => request("/teacher/questions/generate", { method: "POST", body: JSON.stringify(payload) }),
  generationLogs: () => request("/teacher/generation-logs"),
  startComprehensivePractice: () => request("/student/comprehensive-practice/start", { method: "POST" }),
  getNextComprehensiveQuestion: (sessionId) => request(`/student/comprehensive-practice/next?session_id=${sessionId}`),
  submitComprehensiveAnswer: (payload) => request("/student/comprehensive-practice/submit", { method: "POST", body: JSON.stringify(payload) }),
  getComprehensiveSummary: (sessionId) => request(`/student/comprehensive-practice/summary?session_id=${sessionId}`),
};
