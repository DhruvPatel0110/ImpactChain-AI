import React, { useMemo } from 'react';
import { useGlobeStore } from '../../state/globeStore';
import { TIER_CONFIG } from './HighlightLayer';

/**
 * PIN STYLES
 * High-performance CSS for precision location pins on the 3D globe.
 * IMPORTANT: All animations and visual offsets are placed on INNER elements (.pin-inner, .pin-anchor),
 * NEVER on the root container, to avoid conflicting with Three.js CSS2DRenderer's 3D matrix transforms.
 */
export const PIN_MARKER_STYLES = `
  /* Keyframes for ground radar ping */
  @keyframes groundRadarPing {
    0% {
      transform: translate(-50%, -50%) scale(0.4);
      opacity: 0.9;
    }
    50% {
      transform: translate(-50%, -50%) scale(1.6);
      opacity: 0.4;
    }
    100% {
      transform: translate(-50%, -50%) scale(2.4);
      opacity: 0;
    }
  }

  /* Keyframes for pin drop bounce entrance */
  @keyframes pinBounceDrop {
    0% {
      opacity: 0;
      transform: translate(-50%, -160%) scale(0.4);
    }
    60% {
      opacity: 1;
      transform: translate(-50%, -100%) scale(1.12);
    }
    80% {
      transform: translate(-50%, -105%) scale(0.96);
    }
    100% {
      opacity: 1;
      transform: translate(-50%, -100%) scale(1);
    }
  }

  /* Keyframes for pin beacon glow */
  @keyframes beaconGlow {
    0%, 100% {
      filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.8)) drop-shadow(0 4px 12px rgba(0, 0, 0, 0.9));
    }
    50% {
      filter: drop-shadow(0 0 18px rgba(56, 189, 248, 1)) drop-shadow(0 0 28px rgba(59, 130, 246, 0.7)) drop-shadow(0 4px 16px rgba(0, 0, 0, 0.95));
    }
  }

  /* Root container: zero-size anchor strictly positioned by Three.js CSS2D */
  .pin-root-anchor {
    position: relative;
    width: 0;
    height: 0;
    user-select: none;
    pointer-events: auto;
    cursor: pointer;
    z-index: 150;
  }

  /* Inner pin body placed with translateY(-100%) so the tip lands exactly at (lat, lng) */
  .pin-inner-body {
    position: absolute;
    bottom: 0;
    left: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    transform: translate(-50%, -100%);
    animation: pinBounceDrop 0.45s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
    cursor: pointer;
  }

  .pin-inner-body:hover {
    transform: translate(-50%, -105%) scale(1.08);
    transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  .pin-inner-body:hover .pin-hover-tooltip {
    opacity: 1;
    transform: translateX(-50%) translateY(0) scale(1);
    pointer-events: auto;
  }

  /* Ground anchor radar wave */
  .pin-ground-ripple {
    position: absolute;
    top: 0;
    left: 0;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    animation: groundRadarPing 1.6s ease-out infinite;
    pointer-events: none;
  }

  .pin-ground-ripple-2 {
    position: absolute;
    top: 0;
    left: 0;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    animation: groundRadarPing 1.6s ease-out 0.8s infinite;
    pointer-events: none;
  }

  /* Ground anchor center dot */
  .pin-ground-dot {
    position: absolute;
    top: 0;
    left: 0;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    pointer-events: none;
    z-index: 1;
  }

  /* SVG Pin Graphics */
  .pin-svg-graphic {
    animation: beaconGlow 2s ease-in-out infinite;
    transition: filter 0.2s ease;
  }

  /* Permanent Floating Location Badge */
  .pin-location-badge {
    position: absolute;
    bottom: calc(100% + 4px);
    left: 50%;
    transform: translateX(-50%);
    background: rgba(15, 23, 42, 0.94);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(56, 189, 248, 0.4);
    padding: 3px 8px;
    border-radius: 6px;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 11px;
    font-weight: 700;
    color: #f8fafc;
    white-space: nowrap;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.6), 0 0 10px rgba(56, 189, 248, 0.3);
    display: flex;
    align-items: center;
    gap: 4px;
    pointer-events: none;
  }

  /* Detailed Hover Tooltip */
  .pin-hover-tooltip {
    position: absolute;
    bottom: calc(100% + 32px);
    left: 50%;
    transform: translateX(-50%) translateY(6px) scale(0.94);
    opacity: 0;
    transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
    pointer-events: none;
    white-space: nowrap;
    z-index: 250;
  }
`;

/**
 * Creates a DOM element for a Location Pin on the 3D Globe
 */
export function createPinElement(pinData, onPinClick = null) {
  const tierConfig = TIER_CONFIG[pinData.tier] || TIER_CONFIG['critical-active'];
  const accentColor = tierConfig.hex || '#ef4444';

  // 1. Root Anchor Container (zero dimensions, managed by CSS2DRenderer)
  const root = document.createElement('div');
  root.className = 'pin-root-anchor';
  root.setAttribute('data-event-id', pinData.eventId);

  // 2. Ground Radar Ripple Waves
  const ripple1 = document.createElement('div');
  ripple1.className = 'pin-ground-ripple';
  ripple1.style.border = `2px solid ${accentColor}`;
  ripple1.style.background = `radial-gradient(circle, ${accentColor}44 0%, transparent 70%)`;
  root.appendChild(ripple1);

  const ripple2 = document.createElement('div');
  ripple2.className = 'pin-ground-ripple-2';
  ripple2.style.border = `2px solid ${accentColor}`;
  ripple2.style.background = `radial-gradient(circle, ${accentColor}33 0%, transparent 70%)`;
  root.appendChild(ripple2);

  // Ground Centroid Dot
  const groundDot = document.createElement('div');
  groundDot.className = 'pin-ground-dot';
  groundDot.style.background = '#ffffff';
  groundDot.style.boxShadow = `0 0 8px #ffffff, 0 0 16px ${accentColor}`;
  root.appendChild(groundDot);

  // 3. Inner Pin Body Container (lifts up from ground dot)
  const innerBody = document.createElement('div');
  innerBody.className = 'pin-inner-body';

  // Permanent Location Badge
  const locationBadge = document.createElement('div');
  locationBadge.className = 'pin-location-badge';
  locationBadge.innerHTML = `
    <span style="color: ${accentColor}; font-size: 10px;">📍</span>
    <span>${pinData.label || pinData.eventName}</span>
  `;
  innerBody.appendChild(locationBadge);

  // SVG Pin Graphic
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', '36');
  svg.setAttribute('height', '48');
  svg.setAttribute('viewBox', '0 0 36 48');
  svg.setAttribute('class', 'pin-svg-graphic');
  svg.style.overflow = 'visible';

  // SVG Definitions: Gradient & Glow
  const defs = document.createElementNS(svgNS, 'defs');
  const gradient = document.createElementNS(svgNS, 'linearGradient');
  gradient.setAttribute('id', `pinGrad_${pinData.eventId}`);
  gradient.setAttribute('x1', '0%');
  gradient.setAttribute('y1', '0%');
  gradient.setAttribute('x2', '100%');
  gradient.setAttribute('y2', '100%');

  const stop1 = document.createElementNS(svgNS, 'stop');
  stop1.setAttribute('offset', '0%');
  stop1.setAttribute('stop-color', '#ffffff');

  const stop2 = document.createElementNS(svgNS, 'stop');
  stop2.setAttribute('offset', '40%');
  stop2.setAttribute('stop-color', accentColor);

  const stop3 = document.createElementNS(svgNS, 'stop');
  stop3.setAttribute('offset', '100%');
  stop3.setAttribute('stop-color', '#0f172a');

  gradient.appendChild(stop1);
  gradient.appendChild(stop2);
  gradient.appendChild(stop3);
  defs.appendChild(gradient);
  svg.appendChild(defs);

  // Pin Needle Path (Classic precision teardrop pin)
  const path = document.createElementNS(svgNS, 'path');
  path.setAttribute(
    'd',
    'M18 0 C8.06 0 0 8.06 0 18 C0 30.5 16 46.5 17.2 47.6 C17.65 48.1 18.35 48.1 18.8 47.6 C20 46.5 36 30.5 36 18 C36 8.06 27.94 0 18 0 Z'
  );
  path.setAttribute('fill', `url(#pinGrad_${pinData.eventId})`);
  path.setAttribute('stroke', '#ffffff');
  path.setAttribute('stroke-width', '1.5');
  svg.appendChild(path);

  // Center Target Beacon Disc
  const centerCircle = document.createElementNS(svgNS, 'circle');
  centerCircle.setAttribute('cx', '18');
  centerCircle.setAttribute('cy', '17');
  centerCircle.setAttribute('r', '7.5');
  centerCircle.setAttribute('fill', '#0f172a');
  centerCircle.setAttribute('stroke', '#ffffff');
  centerCircle.setAttribute('stroke-width', '1.5');
  svg.appendChild(centerCircle);

  // Center Glowing Core Dot
  const coreCircle = document.createElementNS(svgNS, 'circle');
  coreCircle.setAttribute('cx', '18');
  coreCircle.setAttribute('cy', '17');
  coreCircle.setAttribute('r', '4');
  coreCircle.setAttribute('fill', accentColor);
  svg.appendChild(coreCircle);

  innerBody.appendChild(svg);

  // 4. Hover Tooltip
  const tooltip = document.createElement('div');
  tooltip.className = 'pin-hover-tooltip';
  tooltip.innerHTML = `
    <div style="
      background: rgba(15, 23, 42, 0.98);
      backdrop-filter: blur(14px);
      padding: 10px 14px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.2);
      box-shadow: 0 12px 30px -5px rgba(0, 0, 0, 0.9), 0 0 25px ${accentColor}44;
      color: #fff;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-width: 170px;
    ">
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 6px;">
          <div style="width: 7px; height: 7px; border-radius: 50%; background: ${accentColor}; box-shadow: 0 0 8px ${accentColor};"></div>
          <span style="font-weight: 700; color: #f8fafc; font-size: 13px;">${pinData.eventName}</span>
        </div>
        <span style="
          font-size: 9px;
          font-weight: 800;
          text-transform: uppercase;
          padding: 2px 6px;
          border-radius: 4px;
          background: ${accentColor}22;
          color: ${accentColor};
          border: 1px solid ${accentColor}55;
        ">${tierConfig.badgeText}</span>
      </div>
      <div style="display: flex; align-items: center; gap: 6px; font-size: 11px; color: #cbd5e1;">
        <span style="color: #38bdf8;">📍</span>
        <span style="font-weight: 600;">${pinData.label}</span>
      </div>
      <div style="
        margin-top: 2px;
        padding-top: 6px;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 10px;
        color: #94a3b8;
      ">
        <span>${pinData.lat.toFixed(2)}°, ${pinData.lng.toFixed(2)}°</span>
        <span style="color: #38bdf8; font-weight: 700; letter-spacing: 0.5px;">INSPECT SUPPLY CHAIN ▸</span>
      </div>
    </div>
  `;
  innerBody.appendChild(tooltip);
  root.appendChild(innerBody);

  // 5. Click event handling (with stopPropagation)
  const handleClick = (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (onPinClick) {
      onPinClick(pinData);
    }
  };

  root.addEventListener('click', handleClick);
  innerBody.addEventListener('click', handleClick);

  return root;
}

/**
 * Custom hook to produce the active pin markers for the globe
 */
export function usePinLayer(events, onPinClick = null) {
  const pinnedEventId = useGlobeStore((state) => state.pinnedEventId);

  const pinMarkers = useMemo(() => {
    if (!pinnedEventId) return [];

    const event = events.find((e) => e.id === pinnedEventId);
    if (!event || !event.pinCoordinates) return [];

    return [
      {
        eventId: event.id,
        eventName: event.name,
        tier: event.tier,
        lat: event.pinCoordinates.lat,
        lng: event.pinCoordinates.lng,
        label: event.pinCoordinates.label,
        _markerType: 'pin',
      },
    ];
  }, [events, pinnedEventId]);

  const createPinEl = useMemo(() => {
    return (pin) => createPinElement(pin, onPinClick);
  }, [onPinClick]);

  return { pinMarkers, createPinEl };
}

export default function LocationPin() {
  return <style>{PIN_MARKER_STYLES}</style>;
}
