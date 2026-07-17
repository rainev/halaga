export const peso = (value: number, digits = 2) => new Intl.NumberFormat('en-PH', {
  style: 'currency', currency: 'PHP', minimumFractionDigits: digits, maximumFractionDigits: digits,
}).format(value)

export function compactPeso(value: number | null) {
  if (!Number.isFinite(value)) return 'Not reported'
  const amount = value as number
  if (Math.abs(amount) >= 1e9) return `₱${(amount / 1e9).toFixed(1)}B`
  if (Math.abs(amount) >= 1e6) return `₱${(amount / 1e6).toFixed(1)}M`
  return peso(amount, 0)
}

export const percent = (value: number | null, digits = 1) => Number.isFinite(value)
  ? `${((value as number) * 100).toFixed(digits)}%`
  : 'Not reported'

export function PageHeading({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: React.ReactNode }) {
  return (
    <header className="mb-8 flex flex-col items-start justify-between gap-5 md:flex-row md:items-end">
      <div><p className="text-[11px] font-bold uppercase tracking-[.18em] text-[#1c6b57]">{eyebrow}</p><h1 className="mt-2 max-w-4xl text-4xl font-bold leading-[1.04] tracking-[-.045em] md:text-5xl">{title}</h1><p className="mt-3 max-w-2xl text-sm leading-relaxed text-[#68736f]">{description}</p></div>
      {children}
    </header>
  )
}

export const panel = 'rounded-[20px] border border-[#dfe5df] bg-white shadow-[0_12px_35px_rgba(21,42,34,.05)]'
