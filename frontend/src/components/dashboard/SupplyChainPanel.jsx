import React, { useState, useMemo, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  X,
  ShieldAlert,
  MapPin,
  TrendingUp,
  Activity,
  Layers,
  Clock,
  ExternalLink,
  ChevronRight,
  AlertTriangle,
  Ship,
  Building2,
  Factory,
  Fuel,
  CheckCircle2,
  Radio,
  Share2,
  Download,
  Search,
  Filter,
  Sparkles,
  Info
} from 'lucide-react';
import { useGlobeStore } from '../../state/globeStore';
import { useSupplyChainData } from '../../hooks/useSupplyChainData';
import EntityCard from './EntityCard';

/**
 * Filter category tabs
 */
const TABS = [
  { id: 'all', label: 'All Entities' },
  { id: 'commodity', label: 'Commodities' },
  { id: 'company', label: 'Enterprises' },
  { id: 'industry', label: 'Industries' },
  { id: 'route', label: 'Supply Routes' },
];

/**
 * Status style mapping for transport routes
 */
const ROUTE_STATUS_MAP = {
  Blocked: 'bg-red-500/20 text-red-300 border-red-500/40',
  Congested: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  Diverted: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  Operational: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
};

/**
 * SupplyChainPanel Component (Phase 4 Full-Page Intelligence Dashboard)
 * Immersive, full-screen view opening upon pin drill-down selection.
 */
export default function SupplyChainPanel() {
  const dashboardOpen = useGlobeStore((state) => state.dashboardOpen);
  const setDashboardOpen = useGlobeStore((state) => state.setDashboardOpen);
  const selectedEventId = useGlobeStore((state) => state.selectedEventId);
  const pinnedEventId = useGlobeStore((state) => state.pinnedEventId);

  const activeEventId = selectedEventId || pinnedEventId;
  const { data, loading } = useSupplyChainData(activeEventId);

  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Handle ESC key to return to globe
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && dashboardOpen) {
        setDashboardOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dashboardOpen, setDashboardOpen]);

  // Filter entities by category and search query
  const filteredEntities = useMemo(() => {
    if (!data || !data.affectedEntities) return [];
    return data.affectedEntities.filter((entity) => {
      const matchesTab = activeTab === 'all' || entity.type === activeTab;
      const matchesSearch =
        !searchQuery ||
        entity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        entity.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesTab && matchesSearch;
    });
  }, [data, activeTab, searchQuery]);

  const handleClose = () => {
    setDashboardOpen(false);
  };

  return (
    <AnimatePresence>
      {dashboardOpen && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
          className="fixed inset-0 w-full h-full min-h-screen bg-slate-950 z-50 overflow-y-auto text-slate-100 font-sans select-none scrollbar-thin scrollbar-thumb-slate-800"
        >
          {/* Background Ambient Glows */}
          <div className="fixed top-0 left-1/4 w-[600px] h-[400px] bg-blue-600/10 rounded-full blur-[140px] pointer-events-none" />
          <div className="fixed bottom-0 right-1/4 w-[600px] h-[400px] bg-sky-500/10 rounded-full blur-[140px] pointer-events-none" />

          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* 1. TOP NAVIGATION APP BAR */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          <header className="sticky top-0 z-40 w-full bg-slate-950/85 backdrop-blur-xl border-b border-slate-800/80 px-6 lg:px-12 py-4">
            <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
              {/* Back to 3D Globe Button */}
              <button
                onClick={handleClose}
                className="flex items-center gap-2.5 px-4 py-2 rounded-xl bg-slate-900/90 hover:bg-slate-850 text-slate-200 hover:text-white border border-slate-700/80 transition-all duration-200 shadow-md hover:border-blue-500/50 hover:shadow-blue-500/10 group cursor-pointer"
              >
                <ArrowLeft className="w-4 h-4 text-blue-400 group-hover:-translate-x-0.5 transition-transform" />
                <span className="text-xs font-bold uppercase tracking-wider">Back to 3D Globe</span>
              </button>

              {/* Center Branding */}
              <div className="hidden sm:flex items-center gap-2.5 px-4 py-1.5 rounded-full bg-slate-900/80 border border-slate-800">
                <div className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                </div>
                <span className="text-xs font-extrabold tracking-wide text-white">
                  ImpactChain AI
                </span>
                <span className="text-[10px] px-2 py-0.2 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 font-semibold">
                  Intelligence Layer
                </span>
              </div>

              {/* Right Action Controls */}
              <div className="flex items-center gap-2.5">
                <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
                  <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                  <span className="text-[11px] font-medium">Live Telemetry Feed</span>
                </div>

                <button
                  onClick={handleClose}
                  className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-white border border-slate-800 transition-colors"
                  title="Close (Esc)"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>
          </header>

          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* 2. MAIN PAGE WORKSPACE */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          <main className="max-w-7xl mx-auto px-6 lg:px-12 py-8 space-y-8 relative z-10">
            {loading ? (
              <div className="min-h-[60vh] flex flex-col items-center justify-center space-y-4">
                <div className="w-10 h-10 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-sm font-semibold text-slate-400">
                  Compiling supply chain telemetry & satellite analytics...
                </span>
              </div>
            ) : data ? (
              <>
                {/* ── HERO INTELLIGENCE BANNER ── */}
                <section className="relative p-6 lg:p-8 rounded-3xl bg-gradient-to-br from-slate-900/95 via-slate-900/80 to-blue-950/30 border border-slate-800/90 shadow-2xl overflow-hidden">
                  <div className="absolute top-0 right-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

                  <div className="relative z-10 space-y-4">
                    {/* Event Tag Badges */}
                    <div className="flex flex-wrap items-center gap-2.5">
                      <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-850 border border-slate-700/80 text-xs font-semibold text-sky-300 shadow-sm">
                        <MapPin className="w-3.5 h-3.5 text-sky-400" />
                        <span>{data.region}</span>
                      </div>

                      <div
                        className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-extrabold uppercase tracking-wider shadow-sm ${
                          data.severity === 'Critical'
                            ? 'bg-red-500/20 text-red-300 border-red-500/40'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                        }`}
                      >
                        <ShieldAlert className="w-3.5 h-3.5" />
                        <span>{data.severity} Severity Disruption</span>
                      </div>

                      <div className="text-xs text-slate-400 flex items-center gap-1.5 ml-auto">
                        <Clock className="w-3.5 h-3.5 text-slate-500" />
                        <span>Telemetry updated {data.lastUpdated}</span>
                      </div>
                    </div>

                    {/* Headline Title */}
                    <h1 className="text-2xl lg:text-3xl font-black text-white tracking-tight leading-tight">
                      {data.eventName}
                    </h1>

                    {/* Comprehensive Summary */}
                    <p className="text-sm lg:text-base text-slate-300 leading-relaxed max-w-5xl font-normal">
                      {data.summary}
                    </p>

                    {/* 4-Card Key Performance Metric Strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-4 border-t border-slate-800/80">
                      <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-lg">
                        <span className="text-[11px] uppercase font-bold text-slate-400 tracking-wider">
                          Disruption Index
                        </span>
                        <div className="text-xl font-black text-sky-400 mt-1">
                          {data.disruptionLevel}
                        </div>
                      </div>

                      <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-lg">
                        <span className="text-[11px] uppercase font-bold text-slate-400 tracking-wider">
                          Economic Exposure
                        </span>
                        <div className="text-xl font-black text-amber-400 mt-1">
                          {data.estimatedEconomicImpact}
                        </div>
                      </div>

                      <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-lg">
                        <span className="text-[11px] uppercase font-bold text-slate-400 tracking-wider">
                          Critical Nodes
                        </span>
                        <div className="text-xl font-black text-emerald-400 mt-1">
                          {data.affectedEntities?.length || 0} Affected Entities
                        </div>
                      </div>

                      <div className="p-4 rounded-2xl bg-slate-950/70 border border-slate-800/80 shadow-lg">
                        <span className="text-[11px] uppercase font-bold text-slate-400 tracking-wider">
                          Supply Corridors
                        </span>
                        <div className="text-xl font-black text-purple-400 mt-1">
                          {data.supplyRoutes?.length || 0} Key Trade Routes
                        </div>
                      </div>
                    </div>
                  </div>
                </section>

                {/* ── 2-COLUMN INTELLIGENCE SECTION ── */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
                  {/* LEFT 2 COLUMNS: Affected Entities Grid with Visual Placeholder Images */}
                  <section className="lg:col-span-2 space-y-6">
                    {/* Section Header & Filters */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-800">
                      <div>
                        <h2 className="text-lg font-bold text-white flex items-center gap-2 tracking-tight">
                          <Layers className="w-5 h-5 text-blue-400" />
                          <span>Affected Commodities & Entities</span>
                        </h2>
                        <p className="text-xs text-slate-400 mt-0.5">
                          High-resolution intelligence breakdown of impacted commodities, enterprises, and sectors.
                        </p>
                      </div>

                      {/* Search Bar */}
                      <div className="relative w-full sm:w-64">
                        <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          placeholder="Search entities..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          className="w-full pl-9 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500/70"
                        />
                      </div>
                    </div>

                    {/* Category Filter Pills */}
                    <div className="flex flex-wrap gap-2">
                      {TABS.map((tab) => {
                        const count =
                          tab.id === 'all'
                            ? data.affectedEntities?.length
                            : data.affectedEntities?.filter((e) => e.type === tab.id).length;

                        return (
                          <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold tracking-wide transition-all cursor-pointer ${
                              activeTab === tab.id
                                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/25 border border-blue-400/40'
                                : 'bg-slate-900/90 text-slate-400 hover:text-slate-200 hover:bg-slate-850 border border-slate-800'
                            }`}
                          >
                            <span>{tab.label}</span>
                            {count !== undefined && (
                              <span
                                className={`text-[10px] px-1.5 py-0.2 rounded-full font-extrabold ${
                                  activeTab === tab.id
                                    ? 'bg-blue-800 text-blue-100'
                                    : 'bg-slate-800 text-slate-400'
                                }`}
                              >
                                {count}
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>

                    {/* Rich Entity Cards Grid (With Images) */}
                    {filteredEntities.length > 0 ? (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pt-1">
                        {filteredEntities.map((entity) => (
                          <EntityCard key={entity.id} entity={entity} />
                        ))}
                      </div>
                    ) : (
                      <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 text-sm">
                        No matching entities found in this category.
                      </div>
                    )}
                  </section>

                  {/* RIGHT COLUMN: Corridors & Telemetry Timeline */}
                  <aside className="space-y-6">
                    {/* Key Transport & Trade Corridors */}
                    {data.supplyRoutes && data.supplyRoutes.length > 0 && (
                      <div className="p-5 rounded-2xl bg-slate-900/80 backdrop-blur-xl border border-slate-800 shadow-xl space-y-4">
                        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                            <Ship className="w-4 h-4 text-cyan-400" />
                            <span>Transport Corridors</span>
                          </h3>
                          <span className="text-[11px] font-bold text-slate-400">
                            {data.supplyRoutes.length} Monitored
                          </span>
                        </div>

                        <div className="space-y-2.5">
                          {data.supplyRoutes.map((route, idx) => {
                            const statusStyle =
                              ROUTE_STATUS_MAP[route.status] || ROUTE_STATUS_MAP.Operational;

                            return (
                              <div
                                key={idx}
                                className="p-3 rounded-xl bg-slate-950/70 border border-slate-850 hover:border-slate-700 transition-colors flex items-center justify-between gap-3"
                              >
                                <div className="min-w-0">
                                  <div className="text-xs font-bold text-slate-200 truncate">
                                    {route.name}
                                  </div>
                                  <div className="text-[10px] text-slate-400 mt-0.5">
                                    Risk Rating: <span className="font-semibold text-slate-300">{route.risk}</span>
                                  </div>
                                </div>

                                <span
                                  className={`text-[10px] font-extrabold px-2.5 py-1 rounded-lg border uppercase tracking-wider flex-shrink-0 ${statusStyle}`}
                                >
                                  {route.status}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Disruption Incident Telemetry Timeline */}
                    {data.impactTimeline && data.impactTimeline.length > 0 && (
                      <div className="p-5 rounded-2xl bg-slate-900/80 backdrop-blur-xl border border-slate-800 shadow-xl space-y-4">
                        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                            <Clock className="w-4 h-4 text-indigo-400" />
                            <span>Incident Telemetry</span>
                          </h3>
                          <span className="text-[11px] font-bold text-indigo-400 bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-500/30">
                            Chronological
                          </span>
                        </div>

                        <div className="space-y-3 relative before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
                          {data.impactTimeline.map((item, idx) => (
                            <div key={idx} className="relative pl-6 space-y-1">
                              <div className="absolute left-1 top-1.5 w-2.5 h-2.5 rounded-full bg-blue-500 border-2 border-slate-950 -translate-x-1/2" />
                              <div className="text-[10px] font-extrabold uppercase tracking-wider text-sky-400">
                                {item.time}
                              </div>
                              <p className="text-xs text-slate-300 leading-snug">
                                {item.event}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Intelligence Advisory Card */}
                    <div className="p-5 rounded-2xl bg-gradient-to-br from-blue-950/40 to-slate-900/80 border border-blue-500/20 shadow-xl space-y-3">
                      <div className="flex items-center gap-2 text-blue-400 text-xs font-bold uppercase tracking-wider">
                        <Sparkles className="w-4 h-4" />
                        <span>Predictive Intelligence</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed">
                        ImpactChain AI is monitoring spot prices and freight demurrage across global maritime choke points. All entities update as live geopolitical telemetry arrives.
                      </p>
                      <button
                        onClick={handleClose}
                        className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold tracking-wide transition-all shadow-lg shadow-blue-600/20 cursor-pointer"
                      >
                        Inspect Next Geographic Zone
                      </button>
                    </div>
                  </aside>
                </div>
              </>
            ) : (
              <div className="p-12 text-center text-slate-400">
                No telemetry available for this disruption zone.
              </div>
            )}
          </main>

          {/* ─────────────────────────────────────────────────────────────────── */}
          {/* 3. PAGE FOOTER */}
          {/* ─────────────────────────────────────────────────────────────────── */}
          <footer className="w-full border-t border-slate-800/80 bg-slate-950/90 py-6 px-6 lg:px-12 mt-12">
            <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-400">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-slate-300 font-semibold">
                  ImpactChain AI Phase 4 Intelligence Layer Active
                </span>
              </div>
              <button
                onClick={handleClose}
                className="text-xs font-bold text-sky-400 hover:text-sky-300 transition-colors uppercase tracking-wider"
              >
                ← Return to 3D Globe
              </button>
            </div>
          </footer>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
