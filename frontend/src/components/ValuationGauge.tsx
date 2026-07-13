// Signature element: a number line that plots the market price against the
// model's intrinsic value, over undervalued (left/green) and overvalued
// (right/rose) zones. The gap between the two markers *is* the margin of safety
// — the whole question the app exists to answer, made visible.

const php = (n: number) =>
  new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP', maximumFractionDigits: 2 }).format(n)

const clamp = (v: number, lo = 0, hi = 100) => Math.max(lo, Math.min(hi, v))

export function ValuationGauge({ intrinsic, price }: { intrinsic: number; price: number | null }) {
  if (price == null || price === 0 || intrinsic <= 0) {
    return (
      <p className="mt-5 rounded-lg border border-dashed px-3 py-3 text-[13px] text-muted-foreground">
        Add a current price to see the value gap.
      </p>
    )
  }

  const max = Math.max(intrinsic, price) * 1.18
  const fair = clamp((intrinsic / max) * 100)
  const pricePos = clamp((price / max) * 100)
  const upside = intrinsic / price - 1
  const label =
    upside > 0.05
      ? `${(upside * 100).toFixed(1)}% margin of safety`
      : upside < -0.05
        ? `${(Math.abs(upside) * 100).toFixed(1)}% above fair value`
        : 'Priced at fair value'

  return (
    <div className="mt-6">
      <div className="mb-6 flex items-baseline justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Price vs. value
        </span>
        <span
          className={`font-mono text-xs ${upside > 0.05 ? 'text-success' : upside < -0.05 ? 'text-destructive' : 'text-muted-foreground'}`}
        >
          {label}
        </span>
      </div>

      {/* Price label, above its marker */}
      <div className="relative mb-1.5 h-4">
        <div
          className="absolute -translate-x-1/2 whitespace-nowrap text-[11px] font-semibold text-foreground"
          style={{ left: `${clamp(pricePos, 8, 92)}%` }}
        >
          <span className="tnum font-mono">{php(price)}</span>
          <span className="text-muted-foreground"> price</span>
        </div>
      </div>

      {/* Track: undervalued zone | fair line | overvalued zone */}
      <div className="relative h-2.5 rounded-full bg-muted">
        <div
          className="absolute inset-y-0 left-0 rounded-l-full bg-success/30 motion-safe:transition-[width] motion-safe:duration-700"
          style={{ width: `${fair}%` }}
        />
        <div
          className="absolute inset-y-0 right-0 rounded-r-full bg-destructive/25"
          style={{ left: `${fair}%` }}
        />
        {/* Intrinsic (fair-value) boundary */}
        <div className="absolute -top-1 -bottom-1 w-px bg-primary" style={{ left: `${fair}%` }} />
        {/* Price needle */}
        <div
          className="absolute -top-1.5 -bottom-1.5 w-[3px] -translate-x-1/2 rounded-full bg-foreground shadow-sm motion-safe:transition-[left] motion-safe:duration-700"
          style={{ left: `${pricePos}%` }}
        />
      </div>

      {/* Intrinsic label, below its marker */}
      <div className="relative mt-1.5 h-4">
        <div
          className="absolute -translate-x-1/2 whitespace-nowrap text-[11px] font-semibold text-primary"
          style={{ left: `${clamp(fair, 8, 92)}%` }}
        >
          <span className="tnum font-mono">{php(intrinsic)}</span>
          <span className="text-primary/70"> intrinsic</span>
        </div>
      </div>
    </div>
  )
}
