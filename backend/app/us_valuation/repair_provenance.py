"""Systemic provenance repair for the generated US valuation artifacts.

The generator recorded a precise SEC URL + filed_date + exact form for only a
handful of curated tickers; the other ~194 carry a generic browse-EDGAR link,
a null filed_date, and an ambiguous "10-K / 10-Q" form. Every artifact does,
however, carry `issuer.cik` and `source_financial_statement.accession` — enough
to recover the real provenance from SEC's lightweight submissions JSON.

This script repairs ONLY the provenance fields (url, filed_date, form) in
`source_financial_statement`. It never reads or writes any valuation number, so
it cannot regress a curated result the way re-running the engine would.

    python -m app.us_valuation.repair_provenance --dry-run --tickers AAPL,A,NET,XYZ
    python -m app.us_valuation.repair_provenance            # repair all, write

SEC fair-access: one submissions call per company, throttled, descriptive UA.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "us_valuations"
CACHE = Path("/private/tmp/claude-501/-Users-rainevillaver-Documents-Startups-GoodBehavior/36172e98-51fc-45f1-9418-abda7a769aba/scratchpad/sec_submissions")
UA = "FinSight Research provenance-backfill r.villaver@gmail.com"
THROTTLE_S = 0.15  # < 10 req/s per SEC fair-use


def fetch_submissions(cik: str) -> dict:
    """Fetch (and cache) the SEC submissions JSON for a zero-padded CIK."""
    cik10 = cik.zfill(10)
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"CIK{cik10}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    time.sleep(THROTTLE_S)
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        data = json.loads(raw)
    cached.write_text(json.dumps(data))
    return data


def lookup_accession(subs: dict, accession: str) -> dict | None:
    """Find one accession in submissions.filings.recent -> its date/form/doc."""
    recent = (subs.get("filings") or {}).get("recent") or {}
    accs = recent.get("accessionNumber") or []
    for i, a in enumerate(accs):
        if a == accession:
            return {
                "filed_date": recent.get("filingDate", [None] * len(accs))[i],
                "form": recent.get("form", [None] * len(accs))[i],
                "primary_document": recent.get("primaryDocument", [None] * len(accs))[i],
            }
    return None


def precise_url(cik: str, accession: str, primary_document: str | None) -> str:
    """Build the exact Archives URL; fall back to the filing index if no primary doc."""
    cik_int = str(int(cik))
    acc_nodash = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}"
    if primary_document:
        return f"{base}/{primary_document}"
    return f"{base}/{accession}-index.htm"


def repair_one(path: Path, dry_run: bool) -> dict:
    d = json.loads(path.read_text())
    ticker = path.stem
    cik = (d.get("issuer") or {}).get("cik")
    sfs = d.get("source_financial_statement") or {}
    accession = sfs.get("accession")
    if not cik or not accession:
        return {"ticker": ticker, "status": "skip", "reason": "no cik/accession"}

    subs = fetch_submissions(cik)
    hit = lookup_accession(subs, accession)
    if not hit:
        return {"ticker": ticker, "status": "not_found", "reason": f"accession {accession} not in recent"}

    new_url = precise_url(cik, accession, hit.get("primary_document"))
    before = {"url": sfs.get("url"), "filed_date": sfs.get("filed_date"), "form": sfs.get("form")}
    after = {"url": new_url, "filed_date": hit.get("filed_date"), "form": hit.get("form") or sfs.get("form")}

    changed = before != after
    if changed and not dry_run:
        sfs.update(after)
        d["source_financial_statement"] = sfs
        path.write_text(json.dumps(d, indent=2))
    return {"ticker": ticker, "status": "changed" if changed else "same", "before": before, "after": after}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tickers", help="comma-separated; default = all")
    args = ap.parse_args()

    if args.tickers:
        files = [DATA_ROOT / f"{t.strip()}.json" for t in args.tickers.split(",")]
    else:
        files = sorted(DATA_ROOT.glob("*.json"))

    counts = {"changed": 0, "same": 0, "not_found": 0, "skip": 0}
    for f in files:
        if not f.exists():
            print(f"  MISSING {f.name}")
            continue
        r = repair_one(f, args.dry_run)
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        if r["status"] in ("changed", "not_found", "skip"):
            print(f"[{r['ticker']}] {r['status']}")
            if r["status"] == "changed":
                print(f"    url:   {r['before']['url']}")
                print(f"        -> {r['after']['url']}")
                print(f"    filed: {r['before']['filed_date']} -> {r['after']['filed_date']}   form: {r['before']['form']} -> {r['after']['form']}")
            elif r["status"] != "changed":
                print(f"    {r.get('reason')}")
    print(f"\n{'DRY-RUN ' if args.dry_run else ''}summary: {counts}")


if __name__ == "__main__":
    main()
