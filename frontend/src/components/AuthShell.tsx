import type { ReactNode } from 'react'
import { LineChart } from 'lucide-react'

const MODELS = ['DCF', 'DDM', 'Graham', 'Multiples']
// A quiet ticker strip — subject vernacular used as texture, not decoration.
const TAPE = 'JFC  BDO  AP  MEG  GLO  SCC  MER  BPI  TEL  ALI  SM  URC  '

export function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand panel — the thesis: what's a share really worth? */}
      <div className="relative hidden overflow-hidden bg-[hsl(var(--ink))] text-slate-100 lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <LineChart className="h-5 w-5" />
          </span>
          <span className="font-display text-lg font-bold tracking-tight">
            Halaga<span className="text-primary">.</span>
          </span>
        </div>

        <div className="max-w-md">
          <h2 className="font-display text-4xl font-bold leading-[1.1] tracking-tight">
            Know what a Philippine share is <span className="text-primary">actually</span> worth.
          </h2>
          <p className="mt-4 text-slate-400">
            Value any PSE-listed company four ways, then compare intrinsic value to the market price.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {MODELS.map((m) => (
              <span key={m} className="rounded-full border border-white/15 px-3 py-1 font-mono text-xs text-slate-300">
                {m}
              </span>
            ))}
          </div>
        </div>

        <div className="overflow-hidden">
          <div className="whitespace-nowrap font-mono text-xs tracking-widest text-white/15">{TAPE.repeat(3)}</div>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex items-center justify-center bg-background px-6 py-12">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <span className="font-display text-2xl font-bold tracking-tight">
              Halaga<span className="text-primary">.</span>
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  )
}
