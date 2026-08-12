import { api } from "../api/client";
import { ConnectorHealth } from "../components/ConnectorHealth";
import { EventsTable } from "../components/EventsTable";
import { usePolling } from "../hooks/usePolling";

export function Dashboard(): JSX.Element {
  const health = usePolling(api.health, 10_000);
  const venues = usePolling(api.venues, 15_000);
  const events = usePolling(api.events, 5_000);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>MarketEdge UK</h1>
      <p style={{ color: "#9198a1" }}>
        Milestone 0/1 dashboard — connector health and live-ingested Betfair events. Arbitrage
        opportunities land in Milestone 3.
      </p>
      <ConnectorHealth health={health.data} venues={venues.data} />
      <EventsTable events={events.data} error={events.error} />
    </main>
  );
}
