import type { EventSummary } from "../types";

interface Props {
  events: EventSummary[] | null;
  error: string | null;
}

function MatchConfidenceBadge({ event }: { event: EventSummary }): JSX.Element {
  if (event.match_confidence === null) {
    return <span style={{ color: "#9198a1" }}>—</span>;
  }
  const pct = Math.round(event.match_confidence * 100);
  const color = event.needs_review ? "#d29922" : "#3fb950";
  return (
    <span style={{ color }} title={event.needs_review ? "Below auto-match threshold — review" : "Auto-matched"}>
      {pct}%{event.needs_review ? " (review)" : ""}
    </span>
  );
}

export function EventsTable({ events, error }: Props): JSX.Element {
  return (
    <div className="card">
      <h2>Live-ingested events</h2>
      {error && <p style={{ color: "#f85149" }}>{error}</p>}
      {!error && (events?.length ?? 0) === 0 && (
        <p>
          No events ingested yet. Configure Betfair and/or odds-provider credentials in{" "}
          <code>.env</code> and start <code>worker-ingest</code> to see live prices here.
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
              <th>Match confidence</th>
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
                <td>
                  <MatchConfidenceBadge event={e} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
