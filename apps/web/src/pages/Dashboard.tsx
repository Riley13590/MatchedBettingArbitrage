import { api } from "../api/client";
import { ApiUsageCard } from "../components/ApiUsageCard";
import { ConnectorHealth } from "../components/ConnectorHealth";
import { EventsTable } from "../components/EventsTable";
import { OpportunitiesTable } from "../components/OpportunitiesTable";
import { usePolling } from "../hooks/usePolling";

export function Dashboard(): JSX.Element {
  const health = usePolling(api.health, 10_000);
  const venues = usePolling(api.venues, 15_000);
  const events = usePolling(api.events, 5_000);
  const apiUsage = usePolling(api.apiUsage, 30_000);
  const opportunities = usePolling(api.opportunities, 5_000);

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>MarketEdge UK</h1>
      <p style={{ color: "#9198a1" }}>
        Milestone 0-3 dashboard — connector health, live-ingested events across venues with
        cross-venue match confidence, odds-provider API budget, and paper-mode arbitrage
        opportunities with economics telemetry.
      </p>
      <ConnectorHealth health={health.data} venues={venues.data} />
      <ApiUsageCard usage={apiUsage.data} />
      <OpportunitiesTable opportunities={opportunities.data} error={opportunities.error} />
      <EventsTable events={events.data} error={events.error} />
    </main>
  );
}
