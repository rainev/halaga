import { useCallback, useEffect, useState } from 'react'
import { ExternalLink, RefreshCw } from 'lucide-react'
import { listNews, refreshNews } from '../lib/api'
import type { NewsArticle } from '../lib/types'
import { useAuth } from '../context/AuthContext'
import { PageHeading, panel } from '../lib/format'
import { cn } from '@/lib/utils'

// The publisher is more meaningful to a reader than our internal source tag
// ("gnews"), so show the article's own domain when we can parse it.
function outlet(a: NewsArticle): string {
  try {
    return new URL(a.url).hostname.replace(/^www\./, '')
  } catch {
    return a.source
  }
}

export default function News() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [rows, setRows] = useState<NewsArticle[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(() => {
    return listNews()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
  }, [])

  useEffect(() => {
    load().finally(() => setLoading(false))
  }, [load])

  async function handleRefresh() {
    setRefreshing(true)
    setError(null)
    try {
      await refreshNews() // admin-only; pulls a fresh batch from GNews
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Refresh failed')
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <>
      <PageHeading
        eyebrow="Market news"
        title="The latest, as it breaks."
        description="Raw Philippine market headlines pulled straight from the wire — the same feed that powers your portfolio insights, before any analysis."
      >
        {isAdmin && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex h-11 items-center gap-2 rounded-xl bg-[var(--app-text)] px-4 text-sm font-bold text-[var(--app-bg)] hover:opacity-90 disabled:opacity-60"
          >
            <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
        )}
      </PageHeading>

      {error && (
        <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">
          {error}
        </p>
      )}

      {loading ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : rows.length === 0 ? (
        <div className={cn(panel, 'p-10 text-center text-sm text-[var(--app-muted)]')}>
          No news yet. Headlines appear here as they come in off the feed.
        </div>
      ) : (
        <section className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((a) => (
            <a
              key={a.id}
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(panel, 'group flex flex-col p-5 no-underline transition hover:-translate-y-0.5')}
            >
              <div className="flex items-center justify-between gap-2 text-[11px] text-[var(--app-muted)]">
                <span className="truncate font-mono uppercase tracking-[.08em]">{outlet(a)}</span>
                {a.published_at && (
                  <span className="shrink-0">{new Date(a.published_at).toLocaleDateString()}</span>
                )}
              </div>

              <h2 className="mt-3 text-sm font-semibold leading-snug text-[var(--app-text)]">
                {a.title}
              </h2>
              {a.snippet && (
                <p className="mt-2 line-clamp-4 text-xs leading-relaxed text-[var(--app-muted)]">
                  {a.snippet}
                </p>
              )}

              <div className="mt-4 flex items-center gap-1.5 border-t border-[var(--app-border)] pt-3 text-[11px] text-[var(--app-muted)] group-hover:text-[var(--app-text)]">
                <ExternalLink className="h-3 w-3 shrink-0" />
                <span>Read full story</span>
              </div>
            </a>
          ))}
        </section>
      )}
    </>
  )
}
