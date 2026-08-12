import type { EventSummary, HealthResponse, Venue } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${path} failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => getJson<HealthResponse>("/v1/health"),
  venues: () => getJson<Venue[]>("/v1/venues"),
  events: () => getJson<EventSummary[]>("/v1/events"),
};
