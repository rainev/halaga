"""Seed PSE companies by walking the PH-Stocks/ sector folders.

Each `<Sector>/<Company Name>.xlsx` file becomes one company row; the folder name
is the sector. Tickers come from the curated map below (PSE symbols); anything
not mapped gets a placeholder derived from the name that an admin can correct
later via POST /api/companies (upsert by ticker).

The PH-Stocks folder is mounted read-only at /data/PH-Stocks (see docker-compose).
"""

import os
import re
from pathlib import Path

from ..db import pool
from ..services import company_service

DATA_DIR = Path(os.environ.get("PH_STOCKS_DIR", "/data/PH-Stocks"))

# Best-effort PSE ticker map, keyed by the file/company name in PH-Stocks/.
TICKER_MAP = {
    "First Metro Philippine Equity ETF": "FMETF",
    "BDO": "BDO",
    "EastWest Banking Corp": "EW",
    "PNB": "PNB",
    "Union Bank": "UBP",
    "Alliance Global Group Inc": "AGI",
    "DMCI Holdings, Inc.": "DMC",
    "GT Capital Holdings, Inc.": "GTCAP",
    "Lopez Holdings Corp": "LPZ",
    "Aboitiz Power Corp": "AP",
    "Alsons Consolidated Resources Inc": "ACR",
    "PetroEnergy Resources Corp": "PERC",
    "Semirara Mining and Power Corp": "SCC",
    "Apex Mining Co Inc": "APX",
    "Atok-Big Wedge Co": "AB",
    "Enex Energy Corp": "ENEX",
    "Nickel Asia Corp": "NIKL",
    "Altus Group LTD": "APVI",
    "Megaworld Corp": "MEG",
    "Robinsons Land Corp": "RLC",
    "Rockwell Land Corp": "ROCK",
    "CTS Global Equity Group Inc": "CTS",
    "Haus Talk Inc": "HTI",
    "Italpinas Development Corporation": "IDC",
    "MerryMart Consumer Corp": "MM",
    "Globe Telecom Inc": "GLO",
    "LBC Express Holdings Inc": "LBC",
    "MacroAsia Corp": "MAC",
    "Puregold Price Club Inc": "PGOLD",
}


def _placeholder_ticker(name: str) -> str:
    """Deterministic fallback when a name isn't in TICKER_MAP."""
    return re.sub(r"[^A-Za-z0-9]", "", name).upper()[:8]


def main() -> None:
    if not DATA_DIR.is_dir():
        raise SystemExit(f"PH-Stocks data dir not found: {DATA_DIR}")

    pool.open()
    count = 0
    for sector_dir in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
        sector = sector_dir.name
        for xlsx in sorted(sector_dir.glob("*.xlsx")):
            if xlsx.name.startswith("~$") or xlsx.name.startswith("."):
                continue
            name = xlsx.stem
            ticker = TICKER_MAP.get(name) or _placeholder_ticker(name)
            company_service.upsert(ticker, name, sector, "PHP")
            count += 1
    print(f"Seeded {count} companies from {DATA_DIR}")
    pool.close()


if __name__ == "__main__":
    main()
