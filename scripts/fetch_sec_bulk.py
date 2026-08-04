#!/usr/bin/env python3
"""Download and index SEC bulk XBRL datasets for large-scale ingestion.

SEC publishes the full Companyfacts and submissions datasets as single ZIP
archives. Pulling those once is far cheaper, faster, and more reproducible than
issuing thousands of per-issuer requests below the fair-access ceiling.

The bulk archives are treated as a local *cache*: they live under the git-ignored
``archive/local-cache/sec-bulk`` tree and are never committed or deployed. A
manifest records the source URL, size, remote ``Last-Modified`` and a streamed
SHA-256 so a run can be reproduced or verified.

Usage
-----
    SEC_USER_AGENT='FinSight contact@example.com' \
        python3 scripts/fetch_sec_bulk.py download --dataset companyfacts

    python3 scripts/fetch_sec_bulk.py extract --dataset companyfacts \
        --cik 0000320193 --cik 0000789019 --out archive/local-cache/sec-bulk/extracted

    python3 scripts/fetch_sec_bulk.py status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
BULK_DIR = ROOT / "archive" / "local-cache" / "sec-bulk"

DATASETS = {
    "companyfacts": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
}


def _user_agent() -> str:
    agent = os.environ.get("SEC_USER_AGENT")
    if not agent:
        raise SystemExit(
            "SEC_USER_AGENT is required. Set an identifying application name and "
            "monitored contact, e.g. SEC_USER_AGENT='FinSight contact@example.com'."
        )
    return agent


def _normalize_cik(cik: str) -> str:
    digits = "".join(ch for ch in str(cik) if ch.isdigit())
    if not digits:
        raise ValueError(f"CIK must contain digits: {cik!r}")
    return digits.zfill(10)


def _head(url: str, agent: str) -> dict[str, str]:
    request = Request(url, method="HEAD", headers={"User-Agent": agent})
    with urlopen(request, timeout=60) as response:
        return {key.lower(): value for key, value in response.headers.items()}


def _paths(dataset: str) -> tuple[Path, Path]:
    return BULK_DIR / f"{dataset}.zip", BULK_DIR / f"{dataset}.meta.json"


def download(dataset: str, *, force: bool = False, chunk: int = 1 << 20) -> Path:
    url = DATASETS[dataset]
    agent = _user_agent()
    BULK_DIR.mkdir(parents=True, exist_ok=True)
    dest, meta_path = _paths(dataset)

    remote = _head(url, agent)
    remote_size = int(remote.get("content-length", "0"))
    remote_modified = remote.get("last-modified", "")

    if dest.exists() and meta_path.exists() and not force:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (
            meta.get("last_modified") == remote_modified
            and meta.get("size") == dest.stat().st_size == remote_size
        ):
            print(
                f"[skip] {dataset}: local copy is current "
                f"({remote_size / 1e9:.2f} GB, {remote_modified})."
            )
            return dest

    print(
        f"[download] {dataset}: {remote_size / 1e9:.2f} GB from {url}\n"
        f"           -> {dest}"
    )
    digest = hashlib.sha256()
    tmp = dest.with_suffix(".zip.part")
    request = Request(url, headers={"User-Agent": agent})
    downloaded = 0
    started = time.monotonic()
    last_log = started
    with urlopen(request, timeout=120) as response, tmp.open("wb") as handle:
        while True:
            block = response.read(chunk)
            if not block:
                break
            handle.write(block)
            digest.update(block)
            downloaded += len(block)
            now = time.monotonic()
            if now - last_log >= 5:
                rate = downloaded / (now - started) / 1e6
                pct = (downloaded / remote_size * 100) if remote_size else 0
                print(
                    f"           {downloaded / 1e9:.2f} GB "
                    f"({pct:4.1f}%) at {rate:5.1f} MB/s",
                    flush=True,
                )
                last_log = now
    tmp.replace(dest)
    meta = {
        "dataset": dataset,
        "url": url,
        "size": dest.stat().st_size,
        "sha256": digest.hexdigest(),
        "last_modified": remote_modified,
        "downloaded_seconds": round(time.monotonic() - started, 1),
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(
        f"[done] {dataset}: {meta['size'] / 1e9:.2f} GB in "
        f"{meta['downloaded_seconds']}s  sha256={meta['sha256'][:16]}…"
    )
    return dest


def _member_names(cik: str, dataset: str) -> list[str]:
    """Candidate zip entry names for a CIK within a bulk archive."""
    # Both archives store the primary record as ``CIK##########.json``.
    return [f"CIK{cik}.json"]


def extract(dataset: str, ciks: list[str], out_dir: Path) -> list[Path]:
    dest, _ = _paths(dataset)
    if not dest.exists():
        raise SystemExit(
            f"{dataset}.zip is not downloaded yet. Run: "
            f"python3 scripts/fetch_sec_bulk.py download --dataset {dataset}"
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    suffix = "companyfacts" if dataset == "companyfacts" else "submissions"
    with zipfile.ZipFile(dest) as archive:
        available = set(archive.namelist())
        for raw in ciks:
            cik = _normalize_cik(raw)
            member = next(
                (name for name in _member_names(cik, dataset) if name in available),
                None,
            )
            if member is None:
                print(f"[miss] CIK {cik}: no {dataset} entry in bulk archive.")
                continue
            target = out_dir / f"CIK{cik}-{suffix}.json"
            target.write_bytes(archive.read(member))
            written.append(target)
            print(f"[ok]   CIK {cik} -> {target.name}")
    print(f"[done] extracted {len(written)}/{len(ciks)} {dataset} records.")
    return written


def status() -> None:
    if not BULK_DIR.exists():
        print("No bulk cache yet.")
        return
    for dataset in DATASETS:
        zip_path, meta_path = _paths(dataset)
        if not zip_path.exists():
            print(f"{dataset:13} not downloaded")
            continue
        meta = (
            json.loads(meta_path.read_text(encoding="utf-8"))
            if meta_path.exists()
            else {}
        )
        print(
            f"{dataset:13} {zip_path.stat().st_size / 1e9:5.2f} GB  "
            f"last_modified={meta.get('last_modified', '?')}"
        )


def _read_cik_list(args: argparse.Namespace) -> list[str]:
    ciks = list(args.cik or [])
    if args.cik_file:
        text = Path(args.cik_file).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Accept "TICKER,CIK", "CIK,TICKER", or a bare CIK: pick the
            # field carrying the most digits so one universe file serves both
            # this extractor and the harvester.
            fields = [part.strip() for part in line.split(",") if part.strip()]
            token = max(fields, key=lambda field: sum(ch.isdigit() for ch in field))
            ciks.append(token)
    if not ciks:
        raise SystemExit("Provide --cik and/or --cik-file for extraction.")
    return ciks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_download = sub.add_parser("download", help="Fetch a bulk dataset ZIP.")
    p_download.add_argument("--dataset", choices=DATASETS, required=True)
    p_download.add_argument("--force", action="store_true")

    p_extract = sub.add_parser("extract", help="Pull specific CIKs from a local ZIP.")
    p_extract.add_argument("--dataset", choices=DATASETS, required=True)
    p_extract.add_argument("--cik", action="append")
    p_extract.add_argument("--cik-file")
    p_extract.add_argument("--out", required=True)

    sub.add_parser("status", help="Show cached bulk datasets.")

    args = parser.parse_args()
    if args.command == "download":
        download(args.dataset, force=args.force)
    elif args.command == "extract":
        extract(args.dataset, _read_cik_list(args), Path(args.out))
    elif args.command == "status":
        status()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError) as error:
        raise SystemExit(f"SEC request failed: {error}") from error
