import { useState, useEffect } from 'react';
import mockSupplyChain from '../data/mockSupplyChain.json';

/**
 * Custom hook to retrieve supply chain intelligence for a given event ID.
 *
 * NOTE (Phase 4 -> Phase 5 Seam):
 * Currently returns static mock supply chain data synchronously from `mockSupplyChain.json`.
 * When Phase 5 backend linkage is implemented, this hook can be updated to fetch from
 * `/api/events/{eventId}/analysis` without requiring any changes to UI components.
 *
 * @param {string|null} eventId - Unique event identifier (e.g. 'event_colombia_earthquake')
 * @returns {{ data: Object|null, loading: boolean, error: string|null }}
 */
export function useSupplyChainData(eventId) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!eventId) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    // Simulate micro-latency for realistic UI state transitions
    const timer = setTimeout(() => {
      const eventData = mockSupplyChain[eventId];
      if (eventData) {
        setData(eventData);
        setError(null);
      } else {
        // Fallback default for unknown events
        setData({
          eventId,
          eventName: 'Active Disruption Zone',
          region: 'Global Geographic Region',
          tier: 'major',
          severity: 'Moderate',
          summary: 'Supply chain assessment in progress. Intelligence data is being compiled for this regional sector.',
          estimatedEconomicImpact: 'Evaluating impact...',
          disruptionLevel: '50% Risk Index',
          lastUpdated: new Date().toISOString().replace('T', ' ').substring(0, 16) + ' UTC',
          affectedEntities: [
            {
              id: 'ent_gen_commodities',
              name: 'Regional Commodities & Raw Materials',
              type: 'commodity',
              impact: 'Medium',
              icon: 'Fuel',
              description: 'Primary commodity exports undergoing regional distribution checks.',
              metrics: { label: 'Status', "value": "Monitoring" }
            },
            {
              id: 'ent_gen_logistics',
              name: 'Freight & Port Corridors',
              type: 'route',
              impact: 'Medium',
              icon: 'Ship',
              description: 'Maritime and overland freight lines maintaining standard contingency buffers.',
              metrics: { label: 'Route', "value": "Active" }
            }
          ],
          supplyRoutes: [
            { name: 'Primary Maritime Trade Route', status: 'Operational', risk: 'Medium' }
          ],
          impactTimeline: [
            { time: 'Recent', event: 'Event telemetry registered on ImpactChain AI network' }
          ]
        });
      }
      setLoading(false);
    }, 80);

    return () => clearTimeout(timer);
  }, [eventId]);

  return { data, loading, error };
}

export default useSupplyChainData;
