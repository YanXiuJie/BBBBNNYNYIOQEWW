const labels = {
  high: "High Risk",
  moderate: "Moderate",
  strong: "Strong",
  validated: "Validated",
  template: "Template",
  seed: "Seed",
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
};

export default function StatusBadge({ status }) {
  return <span className={`status-badge ${status}`}>{labels[status] || status}</span>;
}
