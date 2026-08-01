"""Small SEC EDGAR JSON client with fair-access controls and durable caching."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SEC_DATA_ROOT = "https://data.sec.gov"


def normalize_cik(cik: str | int) -> str:
    digits = "".join(character for character in str(cik) if character.isdigit())
    if not digits:
        raise ValueError("CIK must contain digits")
    return digits.zfill(10)


class SecClient:
    """Retrieve SEC JSON below the fair-access ceiling.

    Production callers must pass an identifying User-Agent containing an
    application name and monitored contact address. Cached responses can be
    replayed without network access, which keeps valuation runs reproducible.
    """

    _request_lock = threading.Lock()
    _process_last_request_at = 0.0

    def __init__(
        self,
        *,
        user_agent: str | None,
        cache_dir: str | Path,
        requests_per_second: float = 2.0,
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        if requests_per_second <= 0 or requests_per_second > 5:
            raise ValueError("requests_per_second must be above 0 and no more than 5")
        self.user_agent = (user_agent or "").strip()
        self.cache_dir = Path(cache_dir)
        self.requests_per_second = requests_per_second
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def submissions(self, cik: str | int, *, refresh: bool = False) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        return self._get_json(
            f"{SEC_DATA_ROOT}/submissions/CIK{normalized}.json",
            cache_name=f"CIK{normalized}-submissions.json",
            refresh=refresh,
        )

    def companyfacts(self, cik: str | int, *, refresh: bool = False) -> dict[str, Any]:
        normalized = normalize_cik(cik)
        return self._get_json(
            f"{SEC_DATA_ROOT}/api/xbrl/companyfacts/CIK{normalized}.json",
            cache_name=f"CIK{normalized}-companyfacts.json",
            refresh=refresh,
        )

    def _get_json(self, url: str, *, cache_name: str, refresh: bool) -> dict[str, Any]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / cache_name
        if path.exists() and not refresh:
            try:
                raw = path.read_bytes()
                payload = json.loads(raw.decode("utf-8"))
                self._write_cache_metadata(
                    path,
                    url=url,
                    raw=raw,
                    fetched_at_epoch=None,
                )
                return payload
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Invalid SEC cache file: {path.name}") from exc
        if not self.user_agent or "@" not in self.user_agent:
            raise ValueError(
                "A monitored SEC User-Agent is required for a network fetch "
                "(example: 'FinSight contact@example.com')"
            )

        delay = 1.0 / self.requests_per_second
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with self._request_lock:
                    elapsed = time.monotonic() - self._process_last_request_at
                    if elapsed < delay:
                        time.sleep(delay - elapsed)
                    request = Request(
                        url,
                        headers={
                            "User-Agent": self.user_agent,
                            "Accept": "application/json",
                        },
                    )
                    type(self)._process_last_request_at = time.monotonic()
                    with urlopen(request, timeout=self.timeout_seconds) as response:
                        raw = response.read()
                payload = json.loads(raw.decode("utf-8"))
                path.write_bytes(raw)
                self._write_cache_metadata(
                    path,
                    url=url,
                    raw=raw,
                    fetched_at_epoch=time.time(),
                )
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                time.sleep(min(2**attempt, 8))
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        raise RuntimeError(f"SEC request failed after retries ({digest})") from last_error

    @staticmethod
    def _write_cache_metadata(
        path: Path,
        *,
        url: str,
        raw: bytes,
        fetched_at_epoch: float | None,
    ) -> None:
        metadata_path = path.with_suffix(path.suffix + ".meta.json")
        if metadata_path.exists() and fetched_at_epoch is None:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    f"Invalid SEC cache metadata: {metadata_path.name}"
                ) from exc
            actual_hash = hashlib.sha256(raw).hexdigest()
            if metadata.get("sha256") != actual_hash:
                raise RuntimeError(
                    f"SEC cache hash mismatch: {path.name}"
                )
            return
        metadata = {
            "source_url": url,
            "fetched_at_epoch": fetched_at_epoch,
            "cache_file_mtime_epoch": path.stat().st_mtime,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "provenance_status": (
                "network_fetch_recorded"
                if fetched_at_epoch is not None
                else "existing_cache_hashed_on_replay"
            ),
        }
        metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
