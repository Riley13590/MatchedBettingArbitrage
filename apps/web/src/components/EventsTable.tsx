import type { EventSummary } from "../types";

interface Props {
  events: EventSummary[] | null;
  error: string | null;
}

export function EventsTable({ events, error }: Props): JSX.Element {
  return (
    <div className="card">
      <h2>Live-ingested events</h2>
      {error && <p style={{ color: "#f85149" }}>{error}</p>}
      {!error && (events?.length ?? 0) === 0 && (
        <p>
          No events ingested yet. Configure Betfair credentials in <code>.env</code> and start{" "}
          <code>worker-ingest</code> to see live prices here.
        </p>
      )}
      {(events?.length ?? 0) > 0 && (
        <table>
          <thead>
            <tr>
              <th>Sport</th>
              <th>Competition</th>
              <th>Event</th>
              <th>Start (UTC)</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {events!.map((e) => (
              <tr key={e.id}>
                <td>{e.sport}</td>
                <td>{e.competition}</td>
                <td>
                  {e.home_participant && e.away_participant
                    ? `${e.home_participant} v ${e.away_participant}`
                    : "—"}
                </td>
                <td>{new Date(e.start_time).toLocaleString()}</td>
                <td>{e.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
