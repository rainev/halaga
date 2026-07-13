import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { deleteValuation, listValuations } from '../lib/api'
import type { SavedValuation } from '../lib/types'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

const php = (n: number) =>
  new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP', maximumFractionDigits: 2 }).format(n)

function verdictBadge(v: string | null) {
  const s = (v ?? '').toLowerCase()
  if (s === 'undervalued' || s === 'buy') return <Badge variant="success">{v}</Badge>
  if (s === 'overvalued' || s === 'sell') return <Badge variant="destructive">{v}</Badge>
  if (!v) return <span className="text-muted-foreground">—</span>
  return <Badge variant="muted">{v}</Badge>
}

export default function Saved() {
  const [rows, setRows] = useState<SavedValuation[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listValuations()
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  async function remove(id: number) {
    await deleteValuation(id)
    setRows((rs) => rs.filter((r) => r.id !== id))
  }

  return (
    <section className="space-y-6">
      <header>
        <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">Your work</p>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Saved valuations</h1>
        <p className="mt-1 text-sm text-muted-foreground">{rows.length} saved run(s)</p>
      </header>

      {error && <p className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="py-8 text-sm text-muted-foreground">Loading…</p>
      ) : rows.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          No saved valuations yet. Run one and tick “Save this run”.
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>When</TableHead>
                <TableHead>Model</TableHead>
                <TableHead className="text-right">Intrinsic</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead>Verdict</TableHead>
                <TableHead className="text-right"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="text-muted-foreground">{new Date(r.created_at).toLocaleString()}</TableCell>
                  <TableCell className="font-mono text-xs uppercase">{r.model}</TableCell>
                  <TableCell className="tnum text-right font-mono font-medium">{php(r.result.intrinsic_value)}</TableCell>
                  <TableCell className="tnum text-right font-mono text-muted-foreground">
                    {r.result.current_price != null ? php(r.result.current_price) : '—'}
                  </TableCell>
                  <TableCell>{verdictBadge(r.result.verdict)}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" onClick={() => remove(r.id)} aria-label="Delete">
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </section>
  )
}
