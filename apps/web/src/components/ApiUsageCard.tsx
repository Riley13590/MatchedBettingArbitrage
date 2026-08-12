import type { ApiUsage } from "../types";

interface Props {
  usage: ApiUsage | null;
}

export function ApiUsageCard({ usage }: Props): JSX.Element {
  if (!usage) {
    return (
      <div className="card">
        <h2>Odds-provider API budget</h2>
        <p>Loading…</p>
      </div>
    );
  }

  const pctOfSoft = usage.soft_monthly_budget
    ? Math.min(100, Math.round((usage.credits_used_this_month / usage.soft_monthly_budget) * 100))
    : 0;
  const barColor = usage.over_hard_budget ? "#f85149" : usage.over_soft_budget ? "#d29922" : "#3fb950";

  return (
    <div className="card">
      <h2>Odds-provider API budget ({usage.provider})</h2>
      <p>
        {usage.credits_used_this_month} / {usage.soft_monthly_budget} soft budget used this month
        {usage.remaining_credits_reported !== null &&
          ` — provider reports ${usage.remaining_credits_reported} credits remaining`}
      </p>
      <div style={{ background: "#2a2d34", borderRadius: 4, height: 8, overflow: "hidden" }}>
        <div style={{ width: `${pctOfSoft}%`, background: barColor, height: "100%" }} />
      </div>
      {usage.credits_used_this_month > 0 && (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Sport</th>
              <th>Credits this month</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(usage.credits_by_sport).map(([sport, credits]) => (
              <tr key={sport}>
                <td>{sport}</td>
                <td>{credits}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
