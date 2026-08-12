import type { Opportunity } from "../types";

interface Props {
  opportunities: Opportunity[] | null;
  error: string | null;
}

function statusColor(status: string): string {
  if (status === "ACTIVE") return "#3fb950";
  if (status === "EXPIRED") return "#9198a1";
  return "#d29922";
}

export function OpportunitiesTable({ opportunities, error }: Props): JSX.Element {
  return (
    <div className="card">
      <h2>Arbitrage opportunities (paper mode)</h2>
      {error && <p style={{ color: "#f85149" }}>{error}</p>}
      {!error && (opportunities?.length ?? 0) === 0 && (
        <p>
          No arbitrage detected yet. Requires quotes from at least two venues for the same
          market — start <code>worker-strategy</code> once ingestion has some data flowing.
        </p>
      )}
      {(opportunities?.length ?? 0) > 0 && (
        <table>
          <thead>
            <tr>
              <th>Detected</th>
              <th>Strategy</th>
              <th>Sport</th>
              <th>Market</th>
              <th>Venues</th>
              <th>Net ROI</th>
              <th>Worst-case £</th>
              <th>Executable £ edge</th>
              <th>Quote age (ms)</th>
              <th>Status</th>
              <th>Lifetime (ms)</th>
            </tr>
          </thead>
          <tbody>
            {opportunities!.map((o) => (
              <tr key={o.id}>
                <td>{new Date(o.detected_at).toLocaleTimeString()}</td>
                <td>{o.strategy.replace("arbitrage_", "")}</td>
                <td>{o.sport ?? "—"}</td>
                <td>
                  {o.market_family ?? "—"}
                  {o.time_to_start_bucket ? ` (${o.time_to_start_bucket})` : ""}
                </td>
                <td>{o.venues ?? "—"}</td>
                <td>{o.expected_roi ? `${(Number(o.expected_roi) * 100).toFixed(2)}%` : "—"}</td>
                <td>{o.worst_case_profit ? `£${o.worst_case_profit}` : "—"}</td>
                <td>{o.executable_edge_gbp ? `£${o.executable_edge_gbp}` : "—"}</td>
                <td>{o.quote_age_ms_at_detection ?? "—"}</td>
                <td>
                  <span style={{ color: statusColor(o.status) }}>{o.status}</span>
                </td>
                <td>{o.lifetime_ms ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
