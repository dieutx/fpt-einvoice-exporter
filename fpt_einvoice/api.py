import json
import time
from pathlib import Path
from typing import Any

import httpx

from .constants import BASE_URL, KNOWN_TYPE_LABELS
from .log import eprint


def _read_raw_rows(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as exc:
        raise ValueError(f"Raw JSON không hợp lệ: {path}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"Raw JSON phải là list hóa đơn: {path}")
    return payload


def _write_raw_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_types(requested: str, session: dict[str, Any]) -> list[str]:
    session_types = [x.strip() for x in str(session.get("itype", "")).split(",") if x.strip()]
    if requested == "session":
        result = session_types
    elif requested == "all-known":
        result = list(dict.fromkeys(session_types + list(KNOWN_TYPE_LABELS.keys())))
    else:
        result = [x.strip() for x in requested.split(",") if x.strip()]
    return list(dict.fromkeys(result))


def fetch_invoices(
    client: httpx.Client,
    type_code: str,
    fd: str,
    td: str,
    unl: int,
    page_size: int,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    sleep_func=time.sleep,
    raw_path: Path | None = None,
    resume: bool = False,
) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = _read_raw_rows(raw_path) if resume and raw_path is not None else []
    start = len(all_rows)
    page_no = (start // page_size) if page_size else 0
    if all_rows:
        eprint(f"[resume] {type_code} raw={raw_path} rows={len(all_rows)}")
    while True:
        page_no += 1
        params = {
            "start": start,
            "count": page_size,
            "filter": json.dumps(
                {
                    "fd": fd,
                    "td": td,
                    "type": type_code,
                    "unl": unl,
                },
                ensure_ascii=False,
            ),
            "must_count_total": 2,
        }
        attempts = 0
        while True:
            attempts += 1
            try:
                resp = client.get("/api/sea", params=params)
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code == 429 or status_code >= 500
                if not retryable or attempts >= max_retries + 1:
                    raise
                eprint(
                    f"[retry] {type_code} page={page_no} start={start} "
                    f"status={status_code} attempt={attempts}/{max_retries + 1}"
                )
                sleep_func(retry_delay)
            except httpx.RequestError as exc:
                if attempts >= max_retries + 1:
                    raise
                eprint(
                    f"[retry] {type_code} page={page_no} start={start} "
                    f"error={exc.__class__.__name__} attempt={attempts}/{max_retries + 1}"
                )
                sleep_func(retry_delay)
        payload = resp.json()
        batch = payload.get("data", [])
        eprint(f"[fetch] {type_code} page={page_no} start={start} got={len(batch)}")
        if not batch:
            break
        all_rows.extend(batch)
        if raw_path is not None:
            _write_raw_rows(raw_path, all_rows)
        if len(batch) < page_size:
            break
        start += len(batch)
    return all_rows


def build_client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=BASE_URL,
        timeout=120,
        follow_redirects=True,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
        },
    )
