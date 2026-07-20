import {
  BarChart3,
  BookOpen,
  Brain,
  ClipboardList,
  Database,
  FileQuestion,
  GraduationCap,
  Home,
  Layers,
  PenLine,
  RefreshCcw,
  School,
  Target,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";

import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import LoginPage from "./pages/LoginPage";
import AdaptivePractice from "./pages/student/AdaptivePractice";
import ComprehensivePractice from "./pages/student/ComprehensivePractice";
import DiagnosticTest from "./pages/student/DiagnosticTest";
import KnowledgeMap from "./pages/student/KnowledgeMap";
import ProgressStats from "./pages/student/ProgressStats";
import ReviewMistakes from "./pages/student/ReviewMistakes";
import StudentDashboard from "./pages/student/StudentDashboard";
import StudentProfile from "./pages/student/StudentProfile";
import TopicSelection from "./pages/student/TopicSelection";
import AiQuestionGenerator from "./pages/teacher/AiQuestionGenerator";
import ClassDashboard from "./pages/teacher/ClassDashboard";
import ClassManagement from "./pages/teacher/ClassManagement";
import QuestionBank from "./pages/teacher/QuestionBank";
import StudentDetail from "./pages/teacher/StudentDetail";
import StudentKnowledgeAnalysis from "./pages/teacher/StudentKnowledgeAnalysis";
import StudentManagement from "./pages/teacher/StudentManagement";
import SyllabusManagement from "./pages/teacher/SyllabusManagement";

const studentItems = [
  { id: "student-dashboard", label: "Dashboard", icon: <Home size={18} /> },
  { id: "diagnostic", label: "Diagnostic Test", icon: <ClipboardList size={18} /> },
  { id: "topics", label: "Topic Selection", icon: <Layers size={18} /> },
  { id: "practice", label: "Adaptive Practice", icon: <PenLine size={18} /> },
  { id: "comprehensive", label: "Latihan Menyeluruh", icon: <Target size={18} /> },
  { id: "knowledge-map", label: "Peta Pengetahuan", icon: <Brain size={18} /> },
  { id: "progress", label: "Progress & Stats", icon: <BarChart3 size={18} /> },
  { id: "review", label: "Review Mistakes", icon: <RefreshCcw size={18} /> },
  { id: "profile", label: "Profile", icon: <GraduationCap size={18} /> },
];

const teacherItems = [
  { id: "class-dashboard", label: "Class Dashboard", icon: <BarChart3 size={18} /> },
  { id: "classes", label: "Class Management", icon: <School size={18} /> },
  { id: "students", label: "Student Management", icon: <Users size={18} /> },
  { id: "student-detail", label: "Student Detail", icon: <Brain size={18} /> },
  { id: "knowledge-analysis", label: "Knowledge Analysis", icon: <Target size={18} /> },
  { id: "syllabus", label: "Syllabus", icon: <BookOpen size={18} /> },
  { id: "question-bank", label: "Question Bank", icon: <Database size={18} /> },
  { id: "ai-generator", label: "AI Generator", icon: <FileQuestion size={18} /> },
];

export default function App() {
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [activePage, setActivePage] = useState(user?.role === "teacher" ? "class-dashboard" : "student-dashboard");
  const [selectedSubtopicId, setSelectedSubtopicId] = useState(null);
  const [selectedStudentId, setSelectedStudentId] = useState(null);

  function handleLogin(nextUser) {
    setUser(nextUser);
    setActivePage(nextUser.role === "teacher" ? "class-dashboard" : "student-dashboard");
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setUser(null);
  }

  useEffect(() => {
    window.addEventListener("auth-expired", logout);
    return () => window.removeEventListener("auth-expired", logout);
  }, []);

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  const items = user.role === "teacher" ? teacherItems : studentItems;

  return (
    <div className="app-shell">
      <Sidebar items={items} activePage={activePage} onChange={setActivePage} />
      <div className="workspace">
        <Topbar user={user} onLogout={logout} />
        <main className="main-content">
          {user.role === "student" ? (
            <StudentPages
              activePage={activePage}
              setActivePage={setActivePage}
              selectedSubtopicId={selectedSubtopicId}
              setSelectedSubtopicId={setSelectedSubtopicId}
              user={user}
            />
          ) : (
            <TeacherPages
              activePage={activePage}
              setActivePage={setActivePage}
              selectedStudentId={selectedStudentId}
              setSelectedStudentId={setSelectedStudentId}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function StudentPages({ activePage, setActivePage, selectedSubtopicId, setSelectedSubtopicId, user }) {
  const chooseSubtopic = (id) => {
    setSelectedSubtopicId(id);
    setActivePage("practice");
  };

  if (activePage === "diagnostic") return <DiagnosticTest />;
  if (activePage === "topics") return <TopicSelection onPractice={chooseSubtopic} />;
  if (activePage === "practice") return <AdaptivePractice subtopicId={selectedSubtopicId} />;
  if (activePage === "comprehensive") return <ComprehensivePractice />;
  if (activePage === "knowledge-map") return <KnowledgeMap />;
  if (activePage === "progress") return <ProgressStats />;
  if (activePage === "review") return <ReviewMistakes onPractice={chooseSubtopic} />;
  if (activePage === "profile") return <StudentProfile user={user} />;
  return <StudentDashboard onPractice={chooseSubtopic} onNavigate={setActivePage} />;
}

function TeacherPages({ activePage, setActivePage, selectedStudentId, setSelectedStudentId }) {
  const openStudent = (id) => {
    setSelectedStudentId(id);
    setActivePage("student-detail");
  };

  if (activePage === "classes") return <ClassManagement />;
  if (activePage === "students") return <StudentManagement onOpenStudent={openStudent} />;
  if (activePage === "student-detail") return <StudentDetail studentId={selectedStudentId} />;
  if (activePage === "knowledge-analysis") return <StudentKnowledgeAnalysis studentId={selectedStudentId} />;
  if (activePage === "syllabus") return <SyllabusManagement />;
  if (activePage === "question-bank") return <QuestionBank />;
  if (activePage === "ai-generator") return <AiQuestionGenerator />;
  return <ClassDashboard onOpenStudent={openStudent} />;
}
