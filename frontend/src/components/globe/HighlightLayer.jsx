import React, { useMemo, useState } from 'react';
import { ShieldAlert, Activity, AlertTriangle, Radio, ChevronRight, Eye } from 'lucide-react';
import { useGlobeStore } from '../../state/globeStore';

/**
 * TIER CONFIGURATION
 * Single source of truth for color, animation timing, and visual styling per severity tier.
 */
export const TIER_CONFIG = {
  'critical-active': {
    label: 'Critical Active',
    badgeText: 'CRITICAL',
    badgeColor: 'bg-red-500/20 text-red-400 border-red-500/40',
    color: 'rgb(255, 0, 0)',
    hex: '#ef4444',
    fillColor: 'rgba(255, 0, 0, 0.42)',
    borderColor: 'rgba(255, 50, 50, 0.85)',
    borderWidth: '2.5px',
    glowColor: 'rgba(255, 0, 0, 0.7)',
    pulseClass: 'ring-fast-blink',
    isAnimated: true,
    description: 'Urgent active disruption. Fast blinking alert cycle (0.6s).',
  },
  'major': {
    label: 'Major Ongoing',
    badgeText: 'MAJOR',
    badgeColor: 'bg-red-500/15 text-rose-400 border-rose-500/30',
    color: 'rgb(255, 0, 0)',
    hex: '#f43f5e',
    fillColor: 'rgba(255, 30, 60, 0.38)',
    borderColor: 'rgba(255, 60, 80, 0.78)',
    borderWidth: '2px',
    glowColor: 'rgba(255, 30, 60, 0.55)',
    pulseClass: 'ring-static',
    isAnimated: false,
    description: 'Important ongoing situation. Static red disruption zone.',
  },
  'moderate': {
    label: 'Moderate Impact',
    badgeText: 'MODERATE',
    badgeColor: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    color: 'rgb(255, 165, 0)',
    hex: '#f59e0b',
    fillColor: 'rgba(255, 165, 0, 0.32)',
    borderColor: 'rgba(255, 175, 20, 0.72)',
    borderWidth: '2px',
    glowColor: 'rgba(255, 165, 0, 0.45)',
    pulseClass: 'ring-static',
    isAnimated: false,
    description: 'Relevant regional activity. Static orange disruption zone.',
  },
};

/**
 * Injected CSS Keyframes for High-Performance GPU-accelerated Ring Animations
 */
export const HIGHLIGHT_KEYFRAME_STYLES = `
  @keyframes fastBlink {
    0%, 100% {
      opacity: 0.8;
      box-shadow: 0 0 16px rgba(255, 0, 0, 0.85), inset 0 0 10px rgba(255, 0, 0, 0.5);
      border-color: rgba(255, 50, 50, 0.95);
    }
    50% {
      opacity: 0.15;
      box-shadow: 0 0 3px rgba(255, 0, 0, 0.2), inset 0 0 2px rgba(255, 0, 0, 0.1);
      border-color: rgba(255, 50, 50, 0.3);
    }
  }

  @keyframes radarDotPing {
    0% { transform: scale(0.7); opacity: 0.9; }
    50% { transform: scale(1.3); opacity: 1; }
    100% { transform: scale(0.7); opacity: 0.9; }
  }

  /* Only Critical Active blinks/moves */
  .ring-fast-blink {
    animation: fastBlink 0.6s linear infinite !important;
    will-change: opacity, box-shadow, border-color;
  }

  .ring-core-ping {
    animation: radarDotPing 1.2s ease-in-out infinite !important;
  }

  /* Major and Moderate rings are completely static */
  .ring-static {
    animation: none !important;
    transform: scale(1) !important;
  }

  .ring-core-static {
    animation: none !important;
    transform: scale(1) !important;
  }

  .ring-marker-container {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    user-select: none;
    transform: translate(-50%, -50%);
    pointer-events: auto;
  }

  .ring-marker-container:hover .ring-tooltip {
    opacity: 1;
    transform: translateY(0) scale(1);
    pointer-events: auto;
  }

  .ring-tooltip {
    position: absolute;
    bottom: calc(100% + 10px);
    left: 50%;
    transform: translateX(-50%) translateY(4px) scale(0.95);
    opacity: 0;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: none;
    white-space: nowrap;
    z-index: 100;
  }
`;

/**
 * Creates an HTML/SVG DOM element for a ring marker on the 3D globe surface
 */
export function createRingElement(ring, onSelect = null) {
  const tierConfig = TIER_CONFIG[ring.tier] || TIER_CONFIG['moderate'];
  const size = ring.ringSize || 60;

  // Root wrapper for CSS2D positioning
  const container = document.createElement('div');
  container.className = 'ring-marker-container';
  container.setAttribute('data-event-id', ring.eventId);
  container.setAttribute('data-tier', ring.tier);

  // Outer Animated Ring Circle
  const ringEl = document.createElement('div');
  ringEl.className = tierConfig.pulseClass;
  ringEl.style.width = `${size}px`;
  ringEl.style.height = `${size}px`;
  ringEl.style.borderRadius = '50%';
  ringEl.style.border = `${tierConfig.borderWidth} solid ${tierConfig.borderColor}`;
  ringEl.style.background = `radial-gradient(circle, ${tierConfig.fillColor} 0%, rgba(0,0,0,0.1) 75%, transparent 100%)`;
  ringEl.style.backdropFilter = 'blur(1px)';
  ringEl.style.display = 'flex';
  ringEl.style.alignItems = 'center';
  ringEl.style.justifyContent = 'center';
  ringEl.style.boxSizing = 'border-box';
  ringEl.style.transition = 'transform 0.2s ease';

  // Inner Centroid Radar Dot
  const coreDot = document.createElement('div');
  coreDot.className = tierConfig.isAnimated
    ? 'ring-core-dot ring-core-ping'
    : 'ring-core-dot ring-core-static';
  coreDot.style.width = '6px';
  coreDot.style.height = '6px';
  coreDot.style.borderRadius = '50%';
  coreDot.style.backgroundColor = tierConfig.hex;
  coreDot.style.boxShadow = `0 0 8px ${tierConfig.hex}, 0 0 14px ${tierConfig.hex}`;

  ringEl.appendChild(coreDot);
  container.appendChild(ringEl);

  // Hover Tooltip Box
  const tooltip = document.createElement('div');
  tooltip.className = 'ring-tooltip';
  tooltip.innerHTML = `
    <div style="
      background: rgba(15, 23, 42, 0.95);
      backdrop-filter: blur(12px);
      padding: 8px 12px;
      border-radius: 10px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.8), 0 0 15px ${tierConfig.glowColor};
      color: #fff;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 4px;
    ">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px;">
        <span style="font-weight: 700; color: #f8fafc; font-size: 13px;">${ring.eventName}</span>
        <span style="
          font-size: 9px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 2px 6px;
          border-radius: 4px;
          background: ${ring.tier === 'moderate' ? 'rgba(245, 158, 11, 0.25)' : 'rgba(239, 68, 68, 0.25)'};
          color: ${tierConfig.hex};
          border: 1px solid ${tierConfig.hex}44;
        ">${tierConfig.badgeText}</span>
      </div>
      <div style="display: flex; items-center; justify-content: space-between; font-size: 11px; color: #94a3b8;">
        <span>Region: <b style="color: #cbd5e1;">${ring.country}</b></span>
        <span style="color: #64748b; font-size: 10px;">Lat: ${ring.lat.toFixed(1)}°, Lng: ${ring.lng.toFixed(1)}°</span>
      </div>
    </div>
  `;
  container.appendChild(tooltip);

  // Click handler (Phase 3 readiness)
  if (onSelect) {
    container.addEventListener('click', (e) => {
      e.stopPropagation();
      onSelect(ring);
    });
  }

  return container;
}

/**
 * Flattens array of events with multi-country coordinates into a flat list of ring markers
 */
export function flattenEventsToRings(events) {
  if (!Array.isArray(events)) return [];
  return events.flatMap((event) =>
    (event.coordinates || []).map((coord) => ({
      eventId: event.id,
      eventName: event.name,
      tier: event.tier,
      color: event.color,
      country: coord.country,
      lat: coord.lat,
      lng: coord.lng,
      ringSize: event.ringSize || 60,
      pulseBehavior: event.pulseBehavior || 'steady-pulse',
    }))
  );
}

/**
 * Custom React Hook to manage ring marker dataset and element creation
 */
export function useHighlightLayer(events, onSelectRing = null) {
  const ringMarkers = useMemo(() => flattenEventsToRings(events), [events]);

  const renderRingElement = useMemo(() => {
    return (ring) => createRingElement(ring, onSelectRing);
  }, [onSelectRing]);

  return {
    ringMarkers,
    createRingElement: renderRingElement,
  };
}

/**
 * HighlightLayer Component:
 * - Injects GPU CSS keyframe rules for pulsing animations
 * - Provides an interactive Disruption Zones Intelligence HUD / Legend
 * - Integrates with Zustand store for selectedEventId tracking
 */
export default function HighlightLayer({ events = [], globeRef }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const selectedEventId = useGlobeStore((state) => state.selectedEventId);
  const setSelectedEvent = useGlobeStore((state) => state.setSelectedEvent);

  // Group events by severity tier for HUD breakdown
  const tierSummary = useMemo(() => {
    const summary = {
      critical: events.filter((e) => e.tier === 'critical-active'),
      major: events.filter((e) => e.tier === 'major'),
      moderate: events.filter((e) => e.tier === 'moderate'),
    };
    return summary;
  }, [events]);

  // Quick focus camera to event coordinate
  const handleFocusEvent = (event) => {
    if (!event || !event.coordinates || event.coordinates.length === 0) return;
    const firstCoord = event.coordinates[0];
    setSelectedEvent(event.id);
    if (globeRef && globeRef.current) {
      globeRef.current.pointOfView(
        { lat: firstCoord.lat, lng: firstCoord.lng, altitude: 1.4 },
        1200
      );
    }
  };

  return (
    <>
      {/* Injected CSS Animation Styles */}
      <style>{HIGHLIGHT_KEYFRAME_STYLES}</style>

      {/* TOP-RIGHT: Disruption Zones HUD & Legend */}
      <div className="absolute top-20 right-6 z-20 flex flex-col items-end gap-2 pointer-events-none">
        <div className="bg-slate-900/90 backdrop-blur-md border border-slate-800/90 rounded-2xl shadow-2xl overflow-hidden w-72 transition-all duration-300 pointer-events-auto">
          {/* Header */}
          <div
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center justify-between px-4 py-3 bg-slate-800/50 hover:bg-slate-800/80 cursor-pointer transition-colors border-b border-slate-800"
          >
            <div className="flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-400 animate-pulse" />
              <span className="text-xs font-bold text-slate-100 uppercase tracking-wider">
                Active Disruptions ({events.length})
              </span>
            </div>
            <div className="flex items-center gap-1 text-[10px] text-slate-400">
              <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
              <ChevronRight
                className={`w-3.5 h-3.5 transition-transform duration-200 ${
                  isExpanded ? 'rotate-90' : ''
                }`}
              />
            </div>
          </div>

          {/* Tier Counts Pill Bar */}
          <div className="grid grid-cols-3 gap-1.5 p-2.5 bg-slate-950/40 border-b border-slate-800/60 text-center">
            <div className="flex flex-col items-center py-1.5 px-1 rounded-lg bg-red-950/30 border border-red-500/20">
              <span className="text-[10px] uppercase font-bold text-red-400">Critical</span>
              <span className="text-sm font-extrabold text-red-300">
                {tierSummary.critical.length}
              </span>
            </div>
            <div className="flex flex-col items-center py-1.5 px-1 rounded-lg bg-rose-950/20 border border-rose-500/20">
              <span className="text-[10px] uppercase font-bold text-rose-400">Major</span>
              <span className="text-sm font-extrabold text-rose-300">
                {tierSummary.major.length}
              </span>
            </div>
            <div className="flex flex-col items-center py-1.5 px-1 rounded-lg bg-amber-950/20 border border-amber-500/20">
              <span className="text-[10px] uppercase font-bold text-amber-400">Moderate</span>
              <span className="text-sm font-extrabold text-amber-300">
                {tierSummary.moderate.length}
              </span>
            </div>
          </div>

          {/* Event List with Click-to-Focus */}
          {isExpanded && (
            <div className="max-h-60 overflow-y-auto divide-y divide-slate-800/50 scrollbar-thin scrollbar-thumb-slate-700">
              {events.map((event) => {
                const config = TIER_CONFIG[event.tier] || TIER_CONFIG['moderate'];
                const isSelected = selectedEventId === event.id;

                return (
                  <div
                    key={event.id}
                    onClick={() => handleFocusEvent(event)}
                    className={`p-2.5 flex items-center justify-between hover:bg-slate-800/60 cursor-pointer transition-all ${
                      isSelected ? 'bg-blue-900/30 border-l-2 border-blue-400' : ''
                    }`}
                  >
                    <div className="flex flex-col gap-0.5 min-w-0 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            event.tier === 'critical-active'
                              ? 'bg-red-500 animate-ping'
                              : event.tier === 'major'
                              ? 'bg-red-500'
                              : 'bg-amber-500'
                          }`}
                        />
                        <span className="text-xs font-semibold text-slate-200 truncate">
                          {event.name}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400 pl-3.5 truncate">
                        {event.countries.join(', ')}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <span
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${config.badgeColor}`}
                      >
                        {config.badgeText}
                      </span>
                      <Eye className="w-3.5 h-3.5 text-slate-500 hover:text-slate-200 transition-colors" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Legend Footer */}
          <div className="px-3 py-2 bg-slate-950/60 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-400">
            <div className="flex items-center gap-1">
              <Radio className="w-3 h-3 text-emerald-400" />
              <span>8 Real-Time Event Zones</span>
            </div>
            <span className="text-slate-500">Live Pulse Layer</span>
          </div>
        </div>
      </div>
    </>
  );
}
