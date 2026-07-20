export default function StudentProfile({ user }) {
  return (
    <section className="page-stack">
      <div className="page-title">
        <p className="eyebrow">Profile</p>
        <h2>Akaun Murid</h2>
      </div>
      <div className="card form-grid">
        <label>
          Nama
          <input className="input" value={user.full_name} readOnly />
        </label>
        <label>
          Username
          <input className="input" value={user.username} readOnly />
        </label>
        <label>
          Parent Email
          <input className="input" value={user.parent_email || ""} readOnly />
        </label>
        <label>
          Class ID
          <input className="input" value={user.class_id || ""} readOnly />
        </label>
      </div>
    </section>
  );
}
