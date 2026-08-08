# FinSight US valuation — production backlog

Deferred work: large-but-invisible, blocked, or out-of-scope. Each says *why* it's deferred and what would pull it into
the roadmap. Re-evaluate periodically — don't let items rot here.

## Deferred — large / out-of-scope

- **B1 · IFRS / 20-F foreign filers** (20 engine_errors: UL, NVO, AZN, SAP, NVS, SNY, INFY, BIDU…).
  *Why deferred:* they file **20-F on IFRS**, not 10-K on US-GAAP — the normalizer finds no us-gaap facts. This is a
  whole separate ingestion + IFRS-concept-mapping path, not a fix.
  *Unblocks when:* there's demand for foreign-filer coverage and appetite for an IFRS ingestion track.

- **B2 · Autos & parts archetype** (F, GM, TSLA, PCAR + parts).
  *Why deferred:* captive-finance arms put huge financing debt on the balance sheet; naive FCFF/industrial policy
  mis-values them, and n=3 comparables is too thin to calibrate. TSLA is also a growth outlier.
  *Unblocks when:* an industrial-vs-finance-arm split (segment data) is available, or a dedicated auto policy is
  calibrated on a wider set.

- **B3 · Full-500 publishable-AND-credible.**
  *Why deferred:* not an engineering milestone — it needs sustained **analyst review** of per-issuer assumptions,
  overrides, and candidate archetypes. Tracked as the ongoing F1 workflow, not a deliverable.
  *Unblocks when:* an analyst owns the ratification loop.

- **B4 · Too-few-annual-periods issuers** (13: CRWD, NTES, recently-listed / thin-history ADRs).
  *Why deferred:* genuinely insufficient us-gaap history for a multi-year forecast; forcing it would fabricate a trend.
  *Unblocks when:* a short-history policy (e.g., single-period/steady-state model) is designed, or the issuers age.

## Deferred — quality caveats to revisit (not blockers, but carry review flags)

- **B5 · Conservative fallbacks undervalue growth names.** Residual-income / DDM fallbacks (HD $155, MCD $121, WMT $42)
  are systematically conservative for low-payout / high-growth companies. Fine as `review_required` floors; revisit if
  they're surfaced as headline values.
- **B6 · Candidate archetype cohort contamination.** `specialty_chemicals` mixes industrial chem + household/personal
  care; `internet_digital_services` is META/GOOGL-heavy (n=5); `transportation` mixes rail/airline; `retail` mixes
  discount/franchise. Split + recalibrate before promoting to `pass`.
- **B7 · `sales_to_capital` and dividend-growth are governed policy, not per-issuer.** Documented; refine with
  per-issuer evidence before final publish.

## Notes
- Nothing here is a hidden blocker for the NOW phase. These are explicitly parked so the roadmap stays focused on the
  cheap, visible wins (ship + serve) and the genuinely high-value model work (insurance, REITs).
