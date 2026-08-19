import React, { useState } from 'react';
import { TrendingUp, ArrowUpRight, ShieldAlert, Sparkles, Building, Layers } from 'lucide-react';

/**
 * Category badge styling tokens
 */
const TYPE_CONFIG = {
  commodity: {
    label: 'Commodity',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
  },
  company: {
    label: 'Enterprise',
    badge: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40',
  },
  industry: {
    label: 'Industry Sector',
    badge: 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  },
  route: {
    label: 'Supply Route',
    badge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  },
};

/**
 * Impact severity styling tokens
 */
const IMPACT_CONFIG = {
  Critical: {
    badge: 'bg-red-500/25 text-red-300 border-red-500/50 shadow-red-500/20',
    dot: 'bg-red-500 animate-pulse',
    border: 'border-red-500/30 group-hover:border-red-500/60',
    glow: 'group-hover:shadow-[0_0_25px_rgba(239,68,68,0.15)]',
  },
  High: {
    badge: 'bg-rose-500/25 text-rose-300 border-rose-500/50',
    dot: 'bg-rose-400',
    border: 'border-rose-500/30 group-hover:border-rose-500/60',
    glow: 'group-hover:shadow-[0_0_25px_rgba(244,63,94,0.15)]',
  },
  Medium: {
    badge: 'bg-amber-500/25 text-amber-300 border-amber-500/50',
    dot: 'bg-amber-400',
    border: 'border-slate-800 group-hover:border-amber-500/50',
    glow: 'group-hover:shadow-[0_0_25px_rgba(245,158,11,0.15)]',
  },
  Low: {
    badge: 'bg-emerald-500/25 text-emerald-300 border-emerald-500/50',
    dot: 'bg-emerald-400',
    border: 'border-slate-800 group-hover:border-emerald-500/50',
    glow: 'group-hover:shadow-[0_0_25px_rgba(16,185,129,0.15)]',
  },
};

/**
 * EntityCard Component
 * Displays rich placeholder image preview, entity classification, disruption metrics, and details.
 */
export default function EntityCard({ entity }) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);

  if (!entity) return null;

  const typeStyle = TYPE_CONFIG[entity.type] || TYPE_CONFIG.commodity;
  const impactStyle = IMPACT_CONFIG[entity.impact] || IMPACT_CONFIG.Medium;

  return (
    <div
      className={`group relative flex flex-col justify-between rounded-2xl bg-slate-900/80 backdrop-blur-xl border ${impactStyle.border} ${impactStyle.glow} transition-all duration-300 overflow-hidden shadow-xl hover:-translate-y-1`}
    >
      <div>
        {/* Card Image Banner */}
        <div className="relative w-full h-44 bg-slate-950 overflow-hidden">
          {/* Fallback gradient if loading or offline */}
          <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-850 to-blue-950/40 flex items-center justify-center">
            <span className="text-2xl font-black text-slate-800 tracking-wider uppercase select-none">
              {entity.name?.substring(0, 3)}
            </span>
          </div>

          {!imageError && entity.image && (
            <img
              src={entity.image}
              alt={entity.name}
              loading="lazy"
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageError(true)}
              className={`w-full h-full object-cover object-center transform transition-transform duration-700 group-hover:scale-110 ${
                imageLoaded ? 'opacity-100' : 'opacity-0'
              }`}
            />
          )}

          {/* Image Dark Vignette Gradient Overlays */}
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/30 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-slate-950/60 via-transparent to-slate-950/40" />

          {/* Top Overlaid Badges */}
          <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-2 z-10">
            <span
              className={`text-[10px] font-bold tracking-wider uppercase px-2.5 py-1 rounded-lg backdrop-blur-md border shadow-lg ${typeStyle.badge}`}
            >
              {typeStyle.label}
            </span>

            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg backdrop-blur-md border text-[10px] font-extrabold uppercase tracking-wider shadow-lg ${impactStyle.badge}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${impactStyle.dot}`} />
              <span>{entity.impact}</span>
            </div>
          </div>

          {/* Quick Indicator Icon on Bottom Right of Image */}
          <div className="absolute bottom-2.5 right-3 z-10 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <div className="p-1.5 rounded-full bg-slate-900/90 border border-slate-700 text-sky-400 shadow-md">
              <ArrowUpRight className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* Card Content Body */}
        <div className="p-5">
          <h4 className="text-base font-bold text-slate-100 group-hover:text-white transition-colors line-clamp-1 mb-2 tracking-tight">
            {entity.name}
          </h4>

          <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 mb-4 font-normal">
            {entity.description}
          </p>
        </div>
      </div>

      {/* Card Footer Metric Strip */}
      <div className="px-5 pb-5 pt-0">
        {entity.metrics ? (
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs">
            <span className="text-slate-400 font-medium flex items-center gap-1.5">
              <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
              <span>{entity.metrics.label}:</span>
            </span>
            <span className="font-extrabold text-sky-300 bg-sky-950/80 px-2.5 py-0.5 rounded-md border border-sky-500/30 text-xs">
              {entity.metrics.value}
            </span>
          </div>
        ) : (
          <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/70 border border-slate-800/80 text-xs text-slate-500">
            <span>Operational Telemetry</span>
            <span className="text-emerald-400 font-bold">Monitored</span>
          </div>
        )}
      </div>
    </div>
  );
}
