import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { addHolding, listCompanies, listHoldings, removeHolding } from '../lib/api'
import type { Company, Holding } from '../lib/types'
import { PageHeading, panel } from '../lib/format'
import { cn } from '@/lib/utils'

const inputCls =
  'h-11 rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)] outline-none focus:border-[var(--app-text)]'

export default function Portfolio() {
  const [rows, setRows] = useState<Holding[]>([])
  const [companies, setCompanies] = useState<Company[]>([])
  const [ticker, setTicker] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([listHoldings(), listCompanies()])
      .then(([h, c]) => {
        setRows(h)
        setCompanies(c)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  async function onAdd(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const saved = await addHolding(ticker.trim().toUpperCase())
      setRows((rs) => [saved, ...rs.filter((r) => r.id !== saved.id)])
      setTicker('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add company')
    } finally {
      setSaving(false)
    }
  }

  async function remove(id: number) {
    await removeHolding(id)
    setRows((rs) => rs.filter((r) => r.id !== id))
  }

  return (
    <>
      <PageHeading
        eyebrow="Your portfolio"
        title="What you own."
        description="Add the companies you own — your Insights feed only ever shows news that touches them."
      />

      {error && (
        <p className="mb-4 rounded-xl bg-[hsl(var(--destructive))]/10 px-4 py-3 text-sm text-[hsl(var(--destructive))]">
          {error}
        </p>
      )}

      <form onSubmit={onAdd} className={cn(panel, 'mb-6 flex flex-wrap items-end gap-3 p-5')}>
        <label className="grid flex-1 gap-1.5">
          <span className="text-[9px] font-bold uppercase tracking-[.12em] text-[var(--app-muted)]">
            Add a company you own
          </span>
          <input
            list="tickers"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker — e.g. MEG"
            required
            className={cn(inputCls, 'w-full max-w-xs font-mono uppercase')}
          />
          <datalist id="tickers">
            {companies.map((c) => (
              <option key={c.id} value={c.ticker}>
                {c.name}
              </option>
            ))}
          </datalist>
        </label>
        <button
          type="submit"
          disabled={saving}
          className="flex h-11 items-center gap-2 rounded-xl bg-[var(--app-text)] px-4 text-sm font-bold text-[var(--app-bg)] hover:opacity-90 disabled:opacity-60"
        >
          <Plus className="h-4 w-4" /> {saving ? 'Adding…' : 'Add'}
        </button>
      </form>

      {loading ? (
        <p className="py-10 text-sm text-[var(--app-muted)]">Loading…</p>
      ) : rows.length === 0 ? (
        <div className={cn(panel, 'p-10 text-center text-sm text-[var(--app-muted)]')}>
          No companies yet. Add a ticker above to start your Insights feed.
        </div>
      ) : (
        <div className={cn(panel, 'overflow-hidden')}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--app-border)] text-left text-[9px] uppercase tracking-[.12em] text-[var(--app-muted)]">
                <th className="px-5 py-3 font-bold">Ticker</th>
                <th className="px-5 py-3 font-bold">Company</th>
                <th className="px-5 py-3 font-bold">Sector</th>
                <th className="px-5 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-[var(--app-border)] last:border-0">
                  <td className="px-5 py-3 font-mono font-semibold uppercase">{r.ticker}</td>
                  <td className="px-5 py-3">{r.name}</td>
                  <td className="px-5 py-3 text-[var(--app-muted)]">{r.sector ?? '—'}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => remove(r.id)}
                      aria-label={`Remove ${r.ticker}`}
                      className="text-[var(--app-muted)] hover:text-[hsl(var(--destructive))]"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
