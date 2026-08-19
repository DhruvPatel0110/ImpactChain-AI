import React, { useRef, useEffect, useState, useMemo, useCallback } from 'react';
import GlobeComponent from 'react-globe.gl';
import * as THREE from 'three';
import { useGlobeStore } from '../../state/globeStore';
import { useGlobeInteraction } from './useGlobeInteraction';
import HighlightLayer, { useHighlightLayer } from './HighlightLayer';
import LocationPin, { usePinLayer } from './LocationPin';
import SupplyChainPanel from '../dashboard/SupplyChainPanel';
import mockEvents from '../../data/mockEvents.json';
import {
  Globe as GlobeIcon,
  RotateCcw,
  Compass,
  ShieldAlert,
  Layers,
  MapPin,
  ArrowLeft,
  LayoutDashboard
} from 'lucide-react';

export default function Globe() {
  const globeRef = useRef();
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const selectedRegion = useGlobeStore((state) => state.selectedRegion);
  const selectedRegionName = useGlobeStore((state) => state.selectedRegionName);
  const selectedEventId = useGlobeStore((state) => state.selectedEventId);
  const pinnedEventId = useGlobeStore((state) => state.pinnedEventId);
  const dashboardOpen = useGlobeStore((state) => state.dashboardOpen);
  const setSelectedEvent = useGlobeStore((state) => state.setSelectedEvent);
  const pinEvent = useGlobeStore((state) => state.pinEvent);
  const unpinEvent = useGlobeStore((state) => state.unpinEvent);
  const setDashboardOpen = useGlobeStore((state) => state.setDashboardOpen);
  const resetToWorld = useGlobeStore((state) => state.resetToWorld);

  const {
    countryPolygons,
    countryLabels,
    handlePolygonHover,
    handlePolygonClick,
    handleResetToWorld,
    getPolygonCapColor,
    getPolygonSideColor,
    getPolygonStrokeColor,
  } = useGlobeInteraction(globeRef);

  // Glassmorphic translucent blue ocean material
  const oceanMaterial = useMemo(() => {
    return new THREE.MeshPhongMaterial({
      color: new THREE.Color('#0c2340'), // Rich glassmorphic navy-blue
      emissive: new THREE.Color('#041122'), // Deep interior glow
      specular: new THREE.Color('#38bdf8'), // Crystal specular sheen on curved ocean
      shininess: 35,
      transparent: true,
      opacity: 0.88,
    });
  }, []);

  // ──────────────────────────────────────────────────────────────────────
  // PHASE 3: Ring / HUD click → Instant Pin Drill-Down
  //
  // When an event ring OR HUD item is clicked:
  //   1. Smooth, low-latency camera fly-to (600ms) to exact pin coordinates
  //   2. The ring is replaced with a glowing precision location pin
  // ──────────────────────────────────────────────────────────────────────
  const handleSelectEvent = useCallback(
    (target) => {
      const eventId = target.eventId || target.id;
      const event = mockEvents.find((e) => e.id === eventId);
      if (!event) return;

      const pinCoords =
        event.pinCoordinates ||
        (event.coordinates && event.coordinates[0]) || {
          lat: target.lat,
          lng: target.lng,
        };

      // Snappy camera fly-to (600ms) directly to the pin location
      if (globeRef.current) {
        globeRef.current.pointOfView(
          { lat: pinCoords.lat, lng: pinCoords.lng, altitude: 0.85 },
          600
        );
      }

      // Transition: ring → pin
      pinEvent(event.id, event.name);
    },
    [pinEvent]
  );

  // ──────────────────────────────────────────────────────────────────────
  // PHASE 4: Pin click → Open Supply Chain Dashboard
  //
  // Clicking the pin opens the slide-in SupplyChainPanel while maintaining
  // the globe and pin context in the background.
  // ──────────────────────────────────────────────────────────────────────
  const handlePinClick = useCallback(
    (pinData) => {
      setSelectedEvent(pinData.eventId);
      setDashboardOpen(true);
      console.log('[Phase 4] Pin clicked — opening supply chain dashboard:', pinData);
    },
    [setSelectedEvent, setDashboardOpen]
  );

  // Back from pin → world view
  const handleBackFromPin = useCallback(() => {
    setDashboardOpen(false);
    unpinEvent();
    if (globeRef.current) {
      globeRef.current.pointOfView(
        { lat: 20, lng: 0, altitude: 2.5 },
        800
      );
    }
  }, [unpinEvent, setDashboardOpen]);

  // Ring markers and element generator for Globe HTML layer (Phase 2)
  const { ringMarkers, createRingElement } = useHighlightLayer(mockEvents, handleSelectEvent);

  // Pin markers and element generator for Globe HTML layer (Phase 3)
  const { pinMarkers, createPinEl } = usePinLayer(mockEvents, handlePinClick);

  // Merge ring markers + active pin markers into a single htmlElementsData layer
  const allHtmlMarkers = useMemo(() => {
    return [...ringMarkers, ...pinMarkers];
  }, [ringMarkers, pinMarkers]);

  // Dispatch renderer based on marker type
  const createHtmlElement = useCallback(
    (marker) => {
      if (marker._markerType === 'pin') {
        return createPinEl(marker);
      }
      return createRingElement(marker);
    },
    [createRingElement, createPinEl]
  );

  // Handle window resizing
  useEffect(() => {
    const handleResize = () => {
      setDimensions({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const hasInteractedRef = useRef(false);

  // Configure auto-rotation
  useEffect(() => {
    const stopRotationPermanently = () => {
      if (hasInteractedRef.current) return;
      hasInteractedRef.current = true;

      if (globeRef.current) {
        const controls = globeRef.current.controls();
        if (controls) {
          controls.autoRotate = false;
        }
      }

      window.removeEventListener('mousemove', stopRotationPermanently);
      window.removeEventListener('mousedown', stopRotationPermanently);
      window.removeEventListener('pointerdown', stopRotationPermanently);
      window.removeEventListener('touchstart', stopRotationPermanently);
      window.removeEventListener('wheel', stopRotationPermanently);
      window.removeEventListener('keydown', stopRotationPermanently);
    };

    if (globeRef.current) {
      const controls = globeRef.current.controls();
      if (controls) {
        if (!hasInteractedRef.current) {
          controls.autoRotate = true;
          controls.autoRotateSpeed = 0.5;
          controls.enableZoom = true;
        } else {
          controls.autoRotate = false;
        }

        controls.addEventListener('start', stopRotationPermanently);
      }
    }

    window.addEventListener('mousemove', stopRotationPermanently, { passive: true });
    window.addEventListener('mousedown', stopRotationPermanently, { passive: true });
    window.addEventListener('pointerdown', stopRotationPermanently, { passive: true });
    window.addEventListener('touchstart', stopRotationPermanently, { passive: true });
    window.addEventListener('wheel', stopRotationPermanently, { passive: true });
    window.addEventListener('keydown', stopRotationPermanently, { passive: true });

    return () => {
      window.removeEventListener('mousemove', stopRotationPermanently);
      window.removeEventListener('mousedown', stopRotationPermanently);
      window.removeEventListener('pointerdown', stopRotationPermanently);
      window.removeEventListener('touchstart', stopRotationPermanently);
      window.removeEventListener('wheel', stopRotationPermanently);
      window.removeEventListener('keydown', stopRotationPermanently);
    };
  }, []);

  // Derive current hint text based on drill-down state
  const hintText = useMemo(() => {
    if (dashboardOpen) return 'Supply Chain Intelligence Dashboard active';
    if (selectedRegion === 'event-pin') return '📍 Click the pin or dashboard button to inspect supply chain impact';
    if (selectedRegion === null) return 'Click any disruption ring or continent to drill down';
    if (selectedRegion === 'continent') return 'Click a country to inspect closely';
    if (selectedRegion === 'country') return 'Country selected — click Back to reset';
    return '';
  }, [selectedRegion, dashboardOpen]);

  // Derive current focus label
  const focusLabel = useMemo(() => {
    if (selectedRegion === 'event-pin') {
      return `📍 Event: ${selectedRegionName}`;
    }
    if (selectedRegion === null) return 'World View';
    if (selectedRegion === 'continent') return `Continent: ${selectedRegionName}`;
    if (selectedRegion === 'country') return `Country: ${selectedRegionName}`;
    return 'World View';
  }, [selectedRegion, selectedRegionName]);

  return (
    <div className="relative w-screen h-screen bg-slate-950 overflow-hidden font-sans select-none">
      {/* 3D Globe Canvas - Glassmorphic Blue Ocean Vector Style */}
      <GlobeComponent
        ref={globeRef}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="rgba(2, 6, 23, 1)"
        globeMaterial={oceanMaterial}
        showAtmosphere={true}
        atmosphereColor="#38bdf8"
        atmosphereAltitude={0.16}
        polygonsData={countryPolygons}
        polygonCapColor={getPolygonCapColor}
        polygonSideColor={getPolygonSideColor}
        polygonStrokeColor={getPolygonStrokeColor}
        polygonAltitude={0.006}
        polygonCapCurvatureResolution={2}
        polygonLabel={({ properties, continent }) => `
          <div style="
            background: rgba(15, 23, 42, 0.92);
            backdrop-filter: blur(8px);
            padding: 8px 14px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 13px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.7);
            pointer-events: none;
          ">
            <div style="font-weight: 700; color: #93c5fd; font-size: 14px;">${properties?.name || 'Country'}</div>
            <div style="color: #cbd5e1; font-size: 11px; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px;">Continent: ${continent || 'N/A'}</div>
          </div>
        `}
        onPolygonClick={handlePolygonClick}
        onPolygonHover={handlePolygonHover}
        polygonTransitionDuration={0}
        labelsData={countryLabels}
        labelLat={(d) => d.lat}
        labelLng={(d) => d.lng}
        labelText={(d) => d.name}
        labelSize={0.45}
        labelDotRadius={0.15}
        labelColor={() => 'rgba(210, 220, 240, 0.9)'}
        labelResolution={2}
        labelAltitude={0.012}
        htmlElementsData={allHtmlMarkers}
        htmlLat={(d) => d.lat}
        htmlLng={(d) => d.lng}
        htmlElement={createHtmlElement}
        htmlAltitude={(d) => (d?._markerType === 'pin' ? 0.025 : 0.012)}
      />

      {/* PHASE 2: Event Highlighting Layer & Active Disruptions HUD */}
      <HighlightLayer
        events={mockEvents}
        globeRef={globeRef}
        onSelectEvent={handleSelectEvent}
      />

      {/* PHASE 3: Location Pin CSS Keyframes & Global Styles */}
      <LocationPin />

      {/* PHASE 4: Supply Chain Dashboard Slide-In Panel */}
      <SupplyChainPanel />

      {/* TOP LEFT: Header Title & Branding Overlay */}
      <div className="absolute top-6 left-6 z-10 flex flex-col gap-1.5 pointer-events-none">
        <div className="flex items-center gap-2.5 bg-slate-900/80 backdrop-blur-md px-4 py-2 rounded-xl border border-slate-800 shadow-xl pointer-events-auto">
          <div className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
          </div>
          <span className="font-bold text-white text-base tracking-wide">ImpactChain AI</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 font-medium">
            Intelligence
          </span>
        </div>
        <p className="text-xs text-slate-400 pl-1 font-medium tracking-tight drop-shadow">
          Global Supply Chain Disruption Intelligence
        </p>
      </div>

      {/* TOP RIGHT: Mode Badge */}
      <div className="absolute top-6 right-6 z-10">
        <div className="flex items-center gap-2 bg-slate-900/80 backdrop-blur-md px-3.5 py-2 rounded-xl border border-slate-800 text-slate-200 text-xs font-semibold shadow-lg">
          {dashboardOpen ? (
            <>
              <LayoutDashboard className="w-4 h-4 text-emerald-400" />
              <span className="text-emerald-300 font-bold">Dashboard Mode</span>
            </>
          ) : selectedRegion === 'event-pin' ? (
            <>
              <MapPin className="w-4 h-4 text-sky-400 animate-pulse" />
              <span className="text-sky-300 font-bold">Pin Drill-Down</span>
            </>
          ) : (
            <>
              <GlobeIcon className="w-4 h-4 text-blue-400" />
              <span>Globe Mode</span>
            </>
          )}
        </div>
      </div>

      {/* BOTTOM LEFT: Zoom Level & Active Region Indicator */}
      <div className="absolute bottom-6 left-6 z-10">
        <div className="flex items-center gap-3 bg-slate-900/85 backdrop-blur-md px-4 py-3 rounded-xl border border-slate-800 text-slate-300 text-xs shadow-xl">
          {selectedRegion === 'event-pin' ? (
            <MapPin className="w-4 h-4 text-sky-400" />
          ) : (
            <Compass className="w-4 h-4 text-indigo-400" />
          )}
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
              Current Focus
            </span>
            <span className="font-semibold text-slate-100 text-sm">
              {focusLabel}
            </span>
          </div>
        </div>
      </div>

      {/* BOTTOM CENTER: Navigation Controls */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 flex items-center gap-3">
        {/* Phase 4: Quick-open Dashboard button when an event is pinned */}
        {selectedRegion === 'event-pin' && !dashboardOpen && (
          <button
            onClick={() => setDashboardOpen(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-full font-semibold text-xs transition-all shadow-2xl bg-blue-600 hover:bg-blue-500 text-white ring-4 ring-blue-500/20 hover:scale-105"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            <span>Open Supply Chain Dashboard</span>
          </button>
        )}

        {/* Phase 3: "Back from Pin" button — appears when a pin is active */}
        {selectedRegion === 'event-pin' && (
          <button
            onClick={handleBackFromPin}
            className="flex items-center gap-2.5 px-5 py-2.5 rounded-full font-semibold text-xs transition-all shadow-2xl bg-slate-900/90 hover:bg-slate-800 text-slate-200 border border-slate-700/80 hover:scale-105"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>Back to World View</span>
          </button>
        )}

        {/* Standard "Back to World View" button */}
        {selectedRegion !== 'event-pin' && (
          <button
            onClick={handleResetToWorld}
            className={`flex items-center gap-2.5 px-5 py-2.5 rounded-full font-semibold text-xs transition-all shadow-2xl ${
              selectedRegion !== null
                ? 'bg-blue-600 hover:bg-blue-500 text-white ring-4 ring-blue-500/20 scale-105'
                : 'bg-slate-900/80 hover:bg-slate-800 text-slate-300 border border-slate-700/60'
            }`}
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Back to World View</span>
          </button>
        )}
      </div>

      {/* HELPER HINT OVERLAY */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
        <div className="bg-slate-900/60 backdrop-blur-sm px-3.5 py-1.5 rounded-full border border-slate-800/60 text-slate-400 text-[11px] font-medium tracking-wide">
          {hintText}
        </div>
      </div>
    </div>
  );
}
