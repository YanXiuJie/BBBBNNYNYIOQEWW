import { Play } from "lucide-react";
import { useState } from "react";

import { api } from "../api";

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("amin");
  const [password, setPassword] = useState("password123");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const body = await api.login({ username, password });
      localStorage.setItem("token", body.access_token);
      localStorage.setItem("user", JSON.stringify(body.user));
      onLogin(body.user);
    } catch (err) {
      setError(err.message);
    }
  }

  async function demoLogin(nextUsername) {
    setUsername(nextUsername);
    setPassword("password123");
    setError("");
    try {
      const body = await api.login({ username: nextUsername, password: "password123" });
      localStorage.setItem("token", body.access_token);
      localStorage.setItem("user", JSON.stringify(body.user));
      onLogin(body.user);
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-copy">
        <p className="eyebrow">Next-Gen E-Learning</p>
        <h1>Adaptive Math AI</h1>
        <p>
          Sistem pembelajaran adaptif Matematik Tahun 5 untuk diagnostik, latihan,
          maklum balas Bahasa Melayu dan analitik guru.
        </p>
      </section>
      <form className="card login-card" onSubmit={submit}>
        <h2>Log masuk</h2>
        <label>
          Username
          <input className="input" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          Password
          <input className="input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        <button className="primary-button">Log masuk</button>
        <div className="demo-buttons">
          <button type="button" className="secondary-button" onClick={() => demoLogin("amin")}>
            <Play size={16} /> Student Amin
          </button>
          <button type="button" className="secondary-button" onClick={() => demoLogin("cikgu")}>
            <Play size={16} /> Cikgu Siti
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
      </form>
    </main>
  );
}
