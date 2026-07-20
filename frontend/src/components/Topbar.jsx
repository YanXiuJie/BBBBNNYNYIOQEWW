import { LogOut } from "lucide-react";

export default function Topbar({ user, onLogout }) {
  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{user?.role === "teacher" ? "Teacher/Admin Portal" : "Student Portal"}</p>
        <h1>{user?.role === "teacher" ? "Pengurusan Pembelajaran Adaptif" : "Matematik Tahun 5"}</h1>
      </div>
      <div className="topbar-user">
        <span>{user?.full_name}</span>
        <button className="icon-button" onClick={onLogout} title="Log keluar">
          <LogOut size={18} />
        </button>
      </div>
    </header>
  );
}
