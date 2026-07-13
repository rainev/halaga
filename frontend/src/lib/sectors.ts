// A quiet color per sector — used as small dots so the taxonomy reads at a glance
// without shouting. Muted 500-weight tones on a light surface.
const MAP: Record<string, string> = {
  Financial: 'bg-blue-500',
  Holding: 'bg-violet-500',
  Industrial: 'bg-amber-500',
  'Mining and Oil': 'bg-stone-500',
  Property: 'bg-teal-500',
  Services: 'bg-rose-500',
  ETF: 'bg-slate-500',
  'SME-B': 'bg-emerald-500',
}

export function sectorDot(sector: string | null): string {
  return (sector && MAP[sector]) || 'bg-slate-400'
}
