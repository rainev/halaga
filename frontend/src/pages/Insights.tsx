import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ExternalLink, Info } from 'lucide-react'
import { listInsights } from '../lib/api'
import type { FeedInsight, InsightDirection } from '../lib/types'
import { PageHeading, panel } from '../lib/format'
import { cn } from '@/lib/utils'

// Direction is informational only (how the news could relate to a position) —
// never a recommendation. Styling reflects tone, not advice.
const DIRECTION_LABEL: Record<InsightDirection, string> = {
  headwind: 'Potential headwind',
  tailwind: 'Potential tailwind',
  mixed: 'Mixed',
  neutral: 'Informational',
}

function DirectionTag({ d }: { d: InsightDirection | null }) {
  if (!d) return null
  const tone =
    d === 'tailwind'
      ? 'text-[hsl(var(--success))]'
      : d === 'headwind'
        ? 'text-[hsl(var(--destructive))]'
        : 'text-[var(--app-muted-strong)]'
  return (
    <span className={cn('text-[10px] font-bold uppercase tracking-[.1em]', tone)}>
      {DIRECTION_LABEL[d]}
    </span>
  )
}

export default function Insights() {
  const [rows, setRows] = useState<FeedInsight[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listInsights()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <PageHeading
        eyebrow="Portfolio-aware"
        title="News that touches what you own."
        description="Developments connected to your holdings, and how they could relate to your positions."
      />

      {/* The "awareness, not advice" contract, stated to the user. */}
      <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-[var(--app-border)] bg-[var(--app-subtle)] px-4 py-3 text-xs leading-relaxed text-[var(--app-muted-strong)]">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--app-text)]" />
        <p>
          <strong>Awareness, not advice.</strong> FinSight surfaces information and explains{' '}
          <em>possible</em> impact — it never tells you to buy, sell, or hold. Always check the
          linked source.
        </p>
      </div>

      {error && (
        <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : rows.length === 0 ? (
        <div className={cn(panel, 'p-10 text-center text-sm text-[var(--app-muted)]')}>
          No insights yet. Add companies in your{' '}
          <Link to="/portfolio" className="font-semibold text-[var(--app-text)] underline">
            portfolio
          </Link>{' '}
          — insights appear here as news comes in that touches them.
        </div>
      ) : (
        <section className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((i) => (
            <article key={i.id} className={cn(panel, 'flex flex-col p-5')}>
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="shrink-0 rounded-md bg-[var(--app-subtle)] px-2 py-1 font-mono text-[11px] font-bold uppercase text-[var(--app-text)]">
                    {i.ticker}
                  </span>
                  <span className="truncate text-xs text-[var(--app-muted)]">{i.name}</span>
                </div>
                <DirectionTag d={i.direction} />
              </div>

              <p className="mt-4 text-sm font-semibold leading-snug">{i.summary}</p>
              <p className="mt-2 text-xs leading-relaxed text-[var(--app-muted)]">{i.possible_impact}</p>

              <div className="mt-4 flex items-center justify-between gap-3 border-t border-[var(--app-border)] pt-3 text-[11px] text-[var(--app-muted)]">
                <a
                  href={i.article_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-w-0 items-center gap-1.5 hover:text-[var(--app-text)] hover:underline"
                >
                  <ExternalLink className="h-3 w-3 shrink-0" />
                  <span className="truncate">{i.article_title}</span>
                </a>
                <div className="flex shrink-0 items-center gap-2">
                  {i.link_type === 'thematic' && (
                    <span className="uppercase tracking-[.1em]">Thematic</span>
                  )}
                  {i.published_at && <span>{new Date(i.published_at).toLocaleDateString()}</span>}
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </>
  )
}
