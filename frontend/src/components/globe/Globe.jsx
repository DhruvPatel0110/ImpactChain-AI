import React, { useRef, useEffect, useState } from 'react';
import GlobeComponent from 'react-globe.gl';
import { useGlobeStore } from '../../state/globeStore';
import { useGlobeInteraction } from './useGlobeInteraction';
import { Globe as GlobeIcon, RotateCcw, Compass, ShieldAlert, Layers } from 'lucide-react';

export default function Globe() {
  const globeRef = useRef();
  const [dimensions, setDimensions] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  });

  const selectedRegion = useGlobeStore((state) => state.selectedRegion);
  const selectedRegionName = useGlobeStore((state) => state.selectedRegionName);

  const {
    countryPolygons,
    countryLabels,
    setHoveredPolygon,
    handlePolygonClick,
    handleResetToWorld,
    getPolygonCapColor,
    getPolygonSideColor,
    getPolygonStrokeColor,
  } = useGlobeInteraction(globeRef);

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

  // Configure auto-rotation and orbit controls on mount
  useEffect(() => {
    if (globeRef.current) {
      const controls = globeRef.current.controls();
      if (controls) {
        controls.autoRotate = true;
        controls.autoRotateSpeed = 0.5;
        controls.enableZoom = true;

        // Pause auto-rotation when user starts manipulating camera
        controls.addEventListener('start', () => {
          controls.autoRotate = false;
        });
      }
    }
  }, []);

  return (
    <div className="relative w-screen h-screen bg-slate-950 overflow-hidden font-sans select-none">
      {/* 3D Globe Canvas */}
      <GlobeComponent
        ref={globeRef}
        width={dimensions.width}
        height={dimensions.height}
        globeImageUrl="/assets/globe/earth-day.jpg"
        bumpImageUrl="/assets/globe/earth-topology.png"
        nightSideImageUrl="/assets/globe/earth-night.jpg"
        showAtmosphere={true}
        atmosphereColor="#3b82f6"
        atmosphereAltitude={0.15}
        polygonsData={countryPolygons}
        polygonCapColor={getPolygonCapColor}
        polygonSideColor={getPolygonSideColor}
        polygonStrokeColor={getPolygonStrokeColor}
        polygonAltitude={0.008}
        polygonLabel={({ properties, continent }) => `
          <div style="
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(8px);
            padding: 8px 14px;
            border-radius: 10px;
            border: 1px solid rgba(59, 130, 246, 0.4);
            color: white;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 13px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6);
            pointer-events: none;
          ">
            <div style="font-weight: 700; color: #60a5fa; font-size: 14px;">${properties?.name || 'Country'}</div>
            <div style="color: #94a3b8; font-size: 11px; margin-top: 2px; text-transform: uppercase; letter-spacing: 0.5px;">Continent: ${continent || 'N/A'}</div>
          </div>
        `}
        onPolygonClick={handlePolygonClick}
        onPolygonHover={setHoveredPolygon}
        polygonTransitionDuration={300}
        labelsData={countryLabels}
        labelLat={(d) => d.lat}
        labelLng={(d) => d.lng}
        labelText={(d) => d.name}
        labelSize={0.45}
        labelDotRadius={0.15}
        labelColor={() => 'rgba(255, 255, 255, 0.85)'}
        labelResolution={2}
        labelAltitude={0.012}
      />

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
          <GlobeIcon className="w-4 h-4 text-blue-400 animate-spin-slow" />
          <span>Globe Mode</span>
        </div>
      </div>

      {/* BOTTOM LEFT: Zoom Level & Active Region Indicator */}
      <div className="absolute bottom-6 left-6 z-10">
        <div className="flex items-center gap-3 bg-slate-900/85 backdrop-blur-md px-4 py-3 rounded-xl border border-slate-800 text-slate-300 text-xs shadow-xl">
          <Compass className="w-4 h-4 text-indigo-400" />
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider font-semibold">
              Current Focus
            </span>
            <span className="font-semibold text-slate-100 text-sm">
              {selectedRegion === null && 'World View'}
              {selectedRegion === 'continent' && `Continent: ${selectedRegionName}`}
              {selectedRegion === 'country' && `Country: ${selectedRegionName}`}
            </span>
          </div>
        </div>
      </div>

      {/* BOTTOM CENTER: Back to World View Button */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10">
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
      </div>

      {/* HELPER HINT OVERLAY */}
      <div className="absolute top-20 left-1/2 -translate-x-1/2 z-10 pointer-events-none">
        <div className="bg-slate-900/60 backdrop-blur-sm px-3.5 py-1.5 rounded-full border border-slate-800/60 text-slate-400 text-[11px] font-medium tracking-wide">
          {selectedRegion === null && 'Click any continent to zoom in'}
          {selectedRegion === 'continent' && 'Click a country to inspect closely'}
          {selectedRegion === 'country' && 'Country selected — click Back to reset'}
        </div>
      </div>
    </div>
  );
}
