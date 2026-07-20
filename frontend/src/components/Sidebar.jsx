export default function Sidebar({ items, activePage, onChange }) {
  return (
    <aside className="sidebar">
      <div className="brand">Adaptive Math AI</div>
      <nav className="nav-list">
        {items.map((item) => (
          <button
            className={activePage === item.id ? "nav-item active" : "nav-item"}
            key={item.id}
            onClick={() => onChange(item.id)}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
