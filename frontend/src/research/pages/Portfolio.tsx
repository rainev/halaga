import { useMemo, useState } from 'react'
import { AlertTriangle, BriefcaseBusiness, Plus, Trash2, Undo2 } from 'lucide-react'
import { INDUSTRIAL_COMPANIES } from '../data.js'
import { portfolioCostBasis, portfolioRealizedReturn } from '../engine.js'
import { PageHeading, panel, peso } from '../format'
import { useResearch, type PortfolioLot } from '../ResearchContext'
import { cn } from '@/lib/utils'

function localToday() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

export default function Portfolio() {
  const { lots, addLot, updateLot, removeLot } = useResearch()
  const [showForm, setShowForm] = useState(false)
  const [symbol, setSymbol] = useState('SCC')
  const [quantity, setQuantity] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('')
  const [purchaseDate, setPurchaseDate] = useState(localToday)
  const [saleLotId, setSaleLotId] = useState<string | null>(null)
  const [salePrice, setSalePrice] = useState('')
  const [saleDate, setSaleDate] = useState(localToday)

  const openLots = useMemo(() => lots.filter((lot) => !isSold(lot)), [lots])
  const soldLots = useMemo(() => lots.filter(isSold), [lots])
  const openCost = portfolioCostBasis(openLots)
  const realized = portfolioRealizedReturn(soldLots)
  const allocations = useMemo(() => INDUSTRIAL_COMPANIES.map((company) => ({
    company,
    total: portfolioCostBasis(openLots.filter((lot) => lot.symbol === company.symbol)),
  })).filter((item) => item.total > 0), [openLots])

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const parsedQuantity = Number(quantity)
    const parsedPrice = Number(purchasePrice)
    if (!(parsedQuantity > 0) || !(parsedPrice > 0) || !purchaseDate) return
    addLot({ symbol, quantity: parsedQuantity, purchasePrice: parsedPrice, purchaseDate })
    setQuantity('')
    setPurchasePrice('')
    setPurchaseDate(localToday())
    setShowForm(false)
  }

  function beginSale(lot: PortfolioLot) {
    setSaleLotId(lot.id)
    setSalePrice(lot.salePrice ? String(lot.salePrice) : '')
    setSaleDate(lot.saleDate ?? localToday())
  }

  function recordSale(event: React.FormEvent, lot: PortfolioLot) {
    event.preventDefault()
    const parsedSalePrice = Number(salePrice)
    if (!(parsedSalePrice > 0) || !saleDate || (lot.purchaseDate && saleDate < lot.purchaseDate)) return
    updateLot(lot.id, { salePrice: parsedSalePrice, saleDate })
    setSaleLotId(null)
    setSalePrice('')
    setSaleDate(localToday())
  }

  function deleteSale(lot: PortfolioLot) {
    if (!window.confirm('Delete this sale? The lot will return to open holdings.')) return
    updateLot(lot.id, { salePrice: undefined, saleDate: undefined })
    setSaleLotId(null)
    setSalePrice('')
    setSaleDate(localToday())
  }

  function deleteStock(lot: PortfolioLot) {
    const message = isSold(lot)
      ? 'Delete this stock? This removes both its purchase and sale history.'
      : 'Delete this stock? This removes its purchase history.'
    if (!window.confirm(message)) return
    removeLot(lot.id)
    if (saleLotId === lot.id) setSaleLotId(null)
  }

  return (
    <>
      <PageHeading eyebrow="Portfolio" title="Track buys and sells." description="Save trade dates, costs, and realized returns on this device." />

      <section className="grid gap-3 lg:grid-cols-[.7fr_.7fr_1.25fr]">
        <SummaryCard label="Open cost basis" value={peso(openCost, 0)} note={`${openLots.length} open lot${openLots.length === 1 ? '' : 's'}`} />
        <SummaryCard
          label="Realized return"
          value={soldLots.length ? signedPeso(realized.amount) : '—'}
          note={soldLots.length ? `${signedPercent(realized.percent)} · ${soldLots.length} sold lot${soldLots.length === 1 ? '' : 's'}` : 'No sales recorded'}
        />
        <div className={cn(panel, 'p-6')}>
          <div className="flex justify-between"><h2 className="text-lg font-bold">Open allocation</h2><span className="text-xs text-[var(--app-muted)]">{allocations.length} holdings</span></div>
          {allocations.length ? (
            <div className="mt-5 grid gap-3">
              {allocations.map(({ company, total }) => (
                <div key={company.symbol} className="grid grid-cols-[54px_1fr_44px] items-center gap-3 text-xs">
                  <span className="flex items-center gap-2 font-bold"><i className="h-2 w-2 rounded-full" style={{ background: company.color }} />{company.symbol}</span>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[var(--app-subtle)]"><span className="block h-full rounded-full" style={{ width: `${(total / openCost) * 100}%`, background: company.color }} /></div>
                  <strong className="text-right">{((total / openCost) * 100).toFixed(1)}%</strong>
                </div>
              ))}
            </div>
          ) : <p className="mt-7 text-xs text-[var(--app-muted)]">Add an open lot to see allocation.</p>}
        </div>
      </section>

      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--app-muted)]">Trade history</p><h2 className="mt-1 text-xl font-bold">Your lots</h2></div>
          <button onClick={() => setShowForm((value) => !value)} className="flex h-10 items-center gap-2 rounded-xl bg-[var(--app-text)] px-4 text-xs font-bold text-[var(--app-bg)]"><Plus className="h-4 w-4" /> Add a stock</button>
        </div>

        {showForm && (
          <form onSubmit={submit} className="mb-4 grid items-end gap-3 rounded-2xl border border-[var(--app-border)] bg-[var(--app-subtle)] p-4 md:grid-cols-2 xl:grid-cols-[1.2fr_.7fr_.8fr_.9fr_auto]">
            <Field label="Stock"><select value={symbol} onChange={(event) => setSymbol(event.target.value)} className={inputClass}>{industrialOptions()}</select></Field>
            <Field label="Quantity"><input value={quantity} onChange={(event) => setQuantity(event.target.value)} type="number" min="0.0001" step="any" required placeholder="100" className={inputClass} /></Field>
            <Field label="Buy price (PHP)"><input value={purchasePrice} onChange={(event) => setPurchasePrice(event.target.value)} type="number" min="0.01" step="0.01" required placeholder="32.50" className={inputClass} /></Field>
            <Field label="Date bought"><input value={purchaseDate} onChange={(event) => setPurchaseDate(event.target.value)} type="date" max={localToday()} required className={inputClass} /></Field>
            <button type="submit" className="h-11 rounded-xl bg-[var(--app-text)] px-5 text-xs font-bold text-[var(--app-bg)] md:col-span-2 xl:col-span-1">Save lot</button>
          </form>
        )}

        {lots.length ? (
          <div className="grid gap-3">
            {lots.map((lot) => {
              const company = INDUSTRIAL_COMPANIES.find((item) => item.symbol === lot.symbol) ?? INDUSTRIAL_COMPANIES[0]
              const sold = isSold(lot)
              const lotReturn = sold ? lot.quantity * (Number(lot.salePrice) - lot.purchasePrice) : 0
              const lotPercent = sold ? Number(lot.salePrice) / lot.purchasePrice - 1 : 0
              return (
                <article key={lot.id} className={cn(panel, 'overflow-hidden')}>
                  <div className="grid items-center gap-4 p-4 sm:grid-cols-[1.2fr_1fr_auto]">
                    <div className="flex items-center gap-3">
                      <span className="grid h-10 w-10 place-items-center rounded-xl text-[10px] font-bold text-white" style={{ background: company.color }}>{company.symbol.slice(0, 2)}</span>
                      <span><strong className="block text-sm">{company.symbol}</strong><small className="text-[10px] text-[var(--app-muted)]">{company.shortName}</small></span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                      <LotValue label="QUANTITY" value={lot.quantity.toLocaleString('en-PH')} />
                      <LotValue label="BOUGHT" value={peso(lot.purchasePrice)} />
                      <LotValue label="DATE" value={formatDate(lot.purchaseDate)} />
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <button onClick={() => beginSale(lot)} className="h-9 rounded-xl border border-[var(--app-border)] px-3 text-[10px] font-bold">{sold ? 'Edit sale' : 'Record sale'}</button>
                      {sold && <button onClick={() => deleteSale(lot)} className="flex h-9 items-center gap-1.5 rounded-xl border border-[var(--app-border)] px-3 text-[10px] font-bold text-[var(--app-muted-strong)] hover:bg-[var(--app-subtle)]"><Undo2 className="h-3.5 w-3.5" />Delete sale</button>}
                      <button onClick={() => deleteStock(lot)} aria-label={`Delete ${company.symbol} stock lot`} className="flex h-9 items-center gap-1.5 rounded-xl border border-[var(--app-border)] px-3 text-[10px] font-bold text-[var(--app-muted-strong)] hover:bg-[var(--app-subtle)]"><Trash2 className="h-3.5 w-3.5" />Delete stock</button>
                    </div>
                  </div>

                  {sold && (
                    <div className="grid gap-4 border-t border-[var(--app-border)] bg-[var(--app-subtle)] px-4 py-3 text-xs sm:grid-cols-4">
                      <LotValue label="SOLD" value={peso(Number(lot.salePrice))} />
                      <LotValue label="SALE DATE" value={formatDate(lot.saleDate)} />
                      <LotValue label="RETURN" value={signedPeso(lotReturn)} />
                      <LotValue label="RETURN %" value={signedPercent(lotPercent)} />
                    </div>
                  )}

                  {saleLotId === lot.id && (
                    <form onSubmit={(event) => recordSale(event, lot)} className="grid items-end gap-3 border-t border-[var(--app-border)] bg-[var(--app-subtle)] p-4 sm:grid-cols-[1fr_1fr_auto_auto]">
                      <Field label="Sell price (PHP)"><input value={salePrice} onChange={(event) => setSalePrice(event.target.value)} type="number" min="0.01" step="0.01" required className={inputClass} /></Field>
                      <Field label="Date sold"><input value={saleDate} onChange={(event) => setSaleDate(event.target.value)} type="date" min={lot.purchaseDate || undefined} max={localToday()} required className={inputClass} /></Field>
                      <button type="submit" className="h-11 rounded-xl bg-[var(--app-text)] px-5 text-xs font-bold text-[var(--app-bg)]">Save sale</button>
                      <button type="button" onClick={() => setSaleLotId(null)} className="h-11 rounded-xl border border-[var(--app-border)] px-4 text-xs font-bold">Cancel</button>
                    </form>
                  )}
                </article>
              )
            })}
          </div>
        ) : (
          <div className="grid min-h-64 place-items-center rounded-[20px] border border-dashed border-[var(--app-border)] text-center">
            <div><BriefcaseBusiness className="mx-auto h-8 w-8 text-[var(--app-text)]" /><h2 className="mt-3 text-lg font-bold">No stocks added yet</h2><p className="mt-1 text-xs text-[var(--app-muted)]">Add a purchase to begin your trade history.</p></div>
          </div>
        )}

        <div className="mt-4 flex gap-3 rounded-xl bg-[var(--app-subtle)] p-4 text-xs leading-relaxed text-[var(--app-muted)]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--app-text)]" />
          <p><strong>Return disclaimer:</strong> Realized returns use the buy and sell prices you enter. They are not net of brokerage commissions, taxes, or other transaction fees.</p>
        </div>
      </section>
    </>
  )
}

const inputClass = 'h-11 w-full rounded-xl border border-[var(--app-border)] bg-[var(--app-surface)] px-3 text-sm text-[var(--app-text)]'

function industrialOptions() {
  return INDUSTRIAL_COMPANIES.map((company) => <option key={company.symbol} value={company.symbol}>{company.symbol} · {company.shortName}</option>)
}

function SummaryCard({ label, value, note }: { label: string; value: string; note: string }) {
  return <div className={cn(panel, 'p-6')}><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[var(--app-muted)]">{label}</p><strong className="mt-3 block font-serif text-4xl font-normal tracking-[-.04em]">{value}</strong><p className="mt-2 text-xs text-[var(--app-muted)]">{note}</p></div>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-1 text-[10px] font-bold text-[var(--app-muted)]">{label}{children}</label>
}

function LotValue({ label, value }: { label: string; value: string }) {
  return <div><small className="block text-[8px] font-bold tracking-[.1em] text-[var(--app-muted)]">{label}</small><strong className="mt-1 block text-xs">{value}</strong></div>
}

function isSold(lot: PortfolioLot) {
  return Number.isFinite(lot.salePrice) && Number(lot.salePrice) > 0 && Boolean(lot.saleDate)
}

function formatDate(value?: string) {
  if (!value) return 'Not recorded'
  return new Intl.DateTimeFormat('en-PH', { dateStyle: 'medium' }).format(new Date(`${value}T00:00:00`))
}

function signedPeso(value: number) {
  const amount = peso(Math.abs(value), 0)
  return `${value >= 0 ? '+' : '−'}${amount}`
}

function signedPercent(value: number) {
  return `${value >= 0 ? '+' : '−'}${Math.abs(value * 100).toFixed(1)}%`
}
