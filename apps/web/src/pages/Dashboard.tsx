import { api } from "../api/client";
import { ApiUsageCard } from "../components/ApiUsageCard";
import { ConnectorHealth } from "../components/ConnectorHealth";
import { EventsTable } from "../components/EventsTable";
import { usePolling } from "../hooks/usePolling";

export function Dashboard(): JSX.Element {
  const health = usePolling(api.health, 10_000);
  const venues = usePolling(api.venues, 15_000);
  const events = usePolling(api.events, 5_000);
  const apiUsage = usePolling(api.apiUsage, 30_000);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>MarketEdge UK</h1>
      <p style={{ color: "#9198a1" }}>
        Milestone 0-2 dashboard — connector health, live-ingested events across venues with
        cross-venue match confidence, and odds-provider API budget. Arbitrage opportunities land
        in Milestone 3.
      </p>
      <ConnectorHealth health={health.data} venues={venues.data} />
      <ApiUsageCard usage={apiUsage.data} />
      <EventsTable events={events.data} error={events.error} />
    </main>
  );
}
