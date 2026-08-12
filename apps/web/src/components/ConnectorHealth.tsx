import type { HealthResponse, Venue } from "../types";

interface Props {
  health: HealthResponse | null;
  venues: Venue[] | null;
}

export function ConnectorHealth({ health, venues }: Props): JSX.Element {
  return (
    <div className="card">
      <h2>System</h2>
      <p>
        <span className={`status-dot ${health ? "status-ok" : "status-bad"}`} />
        API: {health ? `${health.status} (mode: ${health.mode})` : "unreachable"}
      </p>
      <table>
        <thead>
          <tr>
            <th>Venue</th>
            <th>Data</th>
            <th>Execution</th>
            <th>Geo status</th>
          </tr>
        </thead>
        <tbody>
          {(venues ?? []).map((v) => (
            <tr key={v.code}>
              <td>{v.name}</td>
              <td>{v.data_allowed ? "yes" : "no"}</td>
              <td>{v.execution_allowed ? "yes" : "no"}</td>
              <td>{v.geo_status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
