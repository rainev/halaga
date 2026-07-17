import { useMemo, useState } from 'react'
import { AlertTriangle, BriefcaseBusiness, Plus, Trash2 } from 'lucide-react'
import { INDUSTRIAL_COMPANIES } from '../data.js'
import { portfolioCostBasis } from '../engine.js'
import { PageHeading, panel, peso } from '../format'
import { useResearch } from '../ResearchContext'
import { cn } from '@/lib/utils'

export default function Portfolio() {
  const { lots, addLot, removeLot } = useResearch()
  const [showForm, setShowForm] = useState(false)
  const [symbol, setSymbol] = useState('SCC')
  const [quantity, setQuantity] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('')
  const total = portfolioCostBasis(lots)
  const allocations = useMemo(() => INDUSTRIAL_COMPANIES.map((company) => ({
    company,
    total: portfolioCostBasis(lots.filter((lot) => lot.symbol === company.symbol)),
  })).filter((item) => item.total > 0), [lots])

  function submit(event: React.FormEvent) {
    event.preventDefault()
    const parsedQuantity = Number(quantity)
    const parsedPrice = Number(purchasePrice)
    if (!(parsedQuantity > 0) || !(parsedPrice > 0)) return
    addLot({ symbol, quantity: parsedQuantity, purchasePrice: parsedPrice })
    setQuantity('')
    setPurchasePrice('')
    setShowForm(false)
  }

  return (
    <>
      <PageHeading eyebrow="Portfolio organizer" title="Remember what you bought." description="Track quantities and purchase cost without publishing or guessing a current price." />
      <section className="grid gap-3 lg:grid-cols-[.7fr_1.3fr]">
        <div className={cn(panel, 'p-6')}><p className="text-[10px] font-bold uppercase tracking-[.15em] text-[#1c6b57]">Total invested at cost</p><strong className="mt-3 block font-serif text-5xl font-normal tracking-[-.04em]">{peso(total, 0)}</strong><p className="mt-2 text-xs text-[#68736f]">{lots.length} lot{lots.length === 1 ? '' : 's'} · saved in this browser</p></div>
        <div className={cn(panel, 'p-6')}><div className="flex justify-between"><h2 className="text-lg font-bold">Cost allocation</h2><span className="text-xs text-[#68736f]">{allocations.length} holdings</span></div>{allocations.length ? <div className="mt-5 grid gap-3">{allocations.map(({ company, total: companyTotal }) => <div key={company.symbol} className="grid grid-cols-[54px_1fr_44px] items-center gap-3 text-xs"><span className="flex items-center gap-2 font-bold"><i className="h-2 w-2 rounded-full" style={{ background: company.color }} />{company.symbol}</span><div className="h-1.5 overflow-hidden rounded-full bg-[#e8ece8]"><span className="block h-full rounded-full" style={{ width: `${(companyTotal / total) * 100}%`, background: company.color }} /></div><strong className="text-right">{((companyTotal / total) * 100).toFixed(1)}%</strong></div>)}</div> : <p className="mt-7 text-xs text-[#68736f]">Add your first lot to see cost allocation.</p>}</div>
      </section>

      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[#1c6b57]">Your lots</p><h2 className="mt-1 text-xl font-bold">Purchase organizer</h2></div><button onClick={() => setShowForm((value) => !value)} className="flex h-10 items-center gap-2 rounded-xl bg-[#1c6b57] px-4 text-xs font-bold text-white"><Plus className="h-4 w-4" /> Add a stock</button></div>
        {showForm && <form onSubmit={submit} className="mb-4 grid items-end gap-3 rounded-2xl border border-[#dfe5df] bg-[#eef1ed] p-4 sm:grid-cols-[1fr_1fr_1fr_auto]"><Field label="Stock"><select value={symbol} onChange={(event) => setSymbol(event.target.value)} className="h-11 rounded-xl border border-[#dfe5df] bg-white px-3 text-sm">{INDUSTRIAL_COMPANIES.map((company) => <option key={company.symbol} value={company.symbol}>{company.symbol} · {company.shortName}</option>)}</select></Field><Field label="Quantity"><input value={quantity} onChange={(event) => setQuantity(event.target.value)} type="number" min="0.0001" step="any" required placeholder="e.g. 100" className="h-11 rounded-xl border border-[#dfe5df] bg-white px-3 text-sm" /></Field><Field label="Purchase price (PHP)"><input value={purchasePrice} onChange={(event) => setPurchasePrice(event.target.value)} type="number" min="0.01" step="0.01" required placeholder="e.g. 32.50" className="h-11 rounded-xl border border-[#dfe5df] bg-white px-3 text-sm" /></Field><button type="submit" className="h-11 rounded-xl bg-[#1c6b57] px-5 text-xs font-bold text-white">Save lot</button></form>}
        {lots.length ? <div className="grid gap-2">{lots.map((lot) => { const company = INDUSTRIAL_COMPANIES.find((item) => item.symbol === lot.symbol) ?? INDUSTRIAL_COMPANIES[0]; return <article key={lot.id} className={cn(panel, 'grid grid-cols-[1fr_80px_36px] items-center gap-3 p-4 sm:grid-cols-[1.2fr_.7fr_.8fr_.8fr_36px]')}><div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl text-[10px] font-bold text-white" style={{ background: company.color }}>{company.symbol.slice(0, 2)}</span><span><strong className="block text-sm">{company.symbol}</strong><small className="text-[10px] text-[#68736f]">{company.shortName}</small></span></div><LotValue label="QUANTITY" value={lot.quantity.toLocaleString('en-PH')} /><LotValue label="PURCHASE PRICE" value={peso(lot.purchasePrice)} hideMobile /><LotValue label="COST BASIS" value={peso(lot.quantity * lot.purchasePrice, 0)} hideMobile /><button onClick={() => removeLot(lot.id)} aria-label={`Remove ${company.symbol} lot`} className="grid h-9 w-9 place-items-center rounded-xl border border-[#dfe5df] text-[#b8493e]"><Trash2 className="h-4 w-4" /></button></article>})}</div> : <div className="grid min-h-64 place-items-center rounded-[20px] border border-dashed border-[#cdd5ce] text-center"><div><BriefcaseBusiness className="mx-auto h-8 w-8 text-[#1c6b57]" /><h2 className="mt-3 text-lg font-bold">No stocks added yet</h2><p className="mt-1 text-xs text-[#68736f]">Add a quantity and purchase price to organize your cost basis.</p></div></div>}
        <div className="mt-4 flex gap-3 rounded-xl bg-[#e9eeea] p-4 text-xs leading-relaxed text-[#5e6965]"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[#1c6b57]" /><p><strong>Why P&amp;L is blank:</strong> Profit or loss requires a current market price. This no-cost mockup intentionally avoids unlicensed or stale quotes.</p></div>
      </section>
    </>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="grid gap-1 text-[10px] font-bold text-[#68736f]">{label}{children}</label> }
function LotValue({ label, value, hideMobile = false }: { label: string; value: string; hideMobile?: boolean }) { return <div className={cn(hideMobile && 'hidden sm:block')}><small className="block text-[8px] font-bold tracking-[.1em] text-[#87938e]">{label}</small><strong className="mt-1 block text-xs">{value}</strong></div> }
