import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Search } from 'lucide-react'
import { listCompanies } from '../lib/api'
import type { Company } from '../lib/types'
import { sectorDot } from '../lib/sectors'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export default function Companies() {
  const navigate = useNavigate()
  const [companies, setCompanies] = useState<Company[]>([])
  const [sector, setSector] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listCompanies()
      .then(setCompanies)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  const sectors = useMemo(
    () => Array.from(new Set(companies.map((c) => c.sector).filter(Boolean))).sort() as string[],
    [companies],
  )

  const visible = companies.filter(
    (c) =>
      (!sector || c.sector === sector) &&
      (!query ||
        c.ticker.toLowerCase().includes(query.toLowerCase()) ||
        c.name.toLowerCase().includes(query.toLowerCase())),
  )

  return (
    <section className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
            Philippine Stock Exchange
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Coverage</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {companies.length} listed companies — pick one to value.
          </p>
        </div>
        <div className="relative w-full max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search ticker or name…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
      </header>

      {/* Sector filter chips — the taxonomy, made tactile */}
      <div className="flex flex-wrap gap-2">
        <Chip active={sector === null} onClick={() => setSector(null)}>All</Chip>
        {sectors.map((s) => (
          <Chip key={s} active={sector === s} onClick={() => setSector(s)}>
            <span className={cn('h-2 w-2 rounded-full', sectorDot(s))} />
            {s}
          </Chip>
        ))}
      </div>

      {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-14 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : (
        <Card className="divide-y overflow-hidden">
          {visible.map((c) => (
            <button
              key={c.id}
              onClick={() => navigate(`/value?company=${c.id}&ticker=${c.ticker}`)}
              className="group flex w-full items-center gap-4 px-4 py-3.5 text-left transition-colors hover:bg-muted/50"
            >
              <span className="tnum w-16 shrink-0 font-mono text-sm font-bold text-foreground">{c.ticker}</span>
              <span className="flex-1 truncate text-sm">{c.name}</span>
              <span className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
                <span className={cn('h-2 w-2 rounded-full', sectorDot(c.sector))} />
                {c.sector ?? '—'}
              </span>
              <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
            </button>
          ))}
          {visible.length === 0 && <p className="p-6 text-sm text-muted-foreground">No companies match your filter.</p>}
        </Card>
      )}
    </section>
  )
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        active
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground',
      )}
    >
      {children}
    </button>
  )
}
