"""FPT API access and crash-safe page checkpoints."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterator
import httpx
from .constants import BASE_URL, KNOWN_TYPE_LABELS
from .log import eprint

def _iter_raw_rows(path: Path) -> Iterator[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            first = fh.read(1); fh.seek(0)
            if first == "[":
                payload = json.load(fh)
                if not isinstance(payload, list): raise ValueError(f"Raw JSON phải là list hóa đơn: {path}")
                for row in payload:
                    if not isinstance(row, dict): raise ValueError(f"Raw JSON phải chứa object: {path}")
                    yield row
                return
            for line_no, line in enumerate(fh, 1):
                if not line.strip(): continue
                try: row = json.loads(line)
                except json.JSONDecodeError as exc: raise ValueError(f"Raw JSONL không hợp lệ: {path}:{line_no}") from exc
                if not isinstance(row, dict): raise ValueError(f"Raw JSONL phải chứa object: {path}:{line_no}")
                yield row
    except FileNotFoundError: return

def _read_raw_rows(path: Path) -> list[dict[str, Any]]: return list(_iter_raw_rows(path))

def _append_raw_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows: return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows: fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        fh.flush(); os.fsync(fh.fileno())

def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True); tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2); fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, path)

def _prepare_raw_checkpoint(path: Path | None, resume: bool) -> list[dict[str, Any]]:
    if path is None: return []
    if not resume:
        path.parent.mkdir(parents=True, exist_ok=True); path.unlink(missing_ok=True); return []
    source = path
    if not source.exists() and path.suffix == ".jsonl" and path.with_suffix(".json").exists(): source = path.with_suffix(".json")
    rows = _read_raw_rows(source) if source.exists() else []
    if source != path or (path.exists() and path.read_text(encoding="utf-8").lstrip().startswith("[")):
        path.unlink(missing_ok=True); _append_raw_rows(path, rows)
        eprint(f"[resume] migrate {source.name} -> {path.name} rows={len(rows)}")
    return rows

def _next_smaller_page_size(page_size: int, minimum: int) -> int:
    for candidate in (500, 100, 10):
        if page_size > candidate >= minimum: return candidate
    return max(minimum, page_size - 1)

def resolve_types(requested: str, session: dict[str, Any]) -> list[str]:
    session_types = [x.strip() for x in str(session.get("itype", "")).split(",") if x.strip()]
    result = session_types if requested == "session" else session_types + list(KNOWN_TYPE_LABELS) if requested == "all-known" else [x.strip() for x in requested.split(",") if x.strip()]
    return list(dict.fromkeys(result))

def _fetch_page(client: httpx.Client, type_code: str, fd: str, td: str, unl: int, start: int, count: int,
                max_retries: int, retry_delay: float, sleep_func=time.sleep) -> list[dict[str, Any]]:
    params = {"start": start, "count": count, "filter": json.dumps({"fd": fd, "td": td, "type": type_code, "unl": unl}, ensure_ascii=False), "must_count_total": 2}
    for attempt in range(1, max_retries + 2):
        try:
            response = client.get("/api/sea", params=params); response.raise_for_status(); rows = response.json().get("data", [])
            if not isinstance(rows, list): raise ValueError(f"API data không phải list: {type_code} start={start}")
            return rows
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code == 429 or exc.response.status_code in (500, 502, 503, 504)
            if not retryable or attempt > max_retries: raise
            eprint(f"[retry] {type_code} start={start} count={count} status={exc.response.status_code} attempt={attempt}/{max_retries + 1}")
        except httpx.RequestError as exc:
            if attempt > max_retries: raise
            eprint(f"[retry] {type_code} start={start} count={count} error={exc.__class__.__name__} attempt={attempt}/{max_retries + 1}")
        sleep_func(retry_delay)
    raise AssertionError("unreachable")

def _page_dir(raw_path: Path) -> Path: return raw_path.parent / (raw_path.name + ".pages")

def _write_page(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_name(path.name + ".tmp"); tmp.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows: fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        fh.flush(); os.fsync(fh.fileno())
    os.replace(tmp, path)

def _assemble_pages(raw_path: Path, pages_dir: Path, last_page: int) -> int:
    tmp = raw_path.with_name(raw_path.name + ".tmp"); count = 0
    with tmp.open("w", encoding="utf-8") as out:
        for page_no in range(last_page + 1):
            page_path = pages_dir / f"{page_no:09d}.jsonl"
            if not page_path.exists(): raise RuntimeError(f"Thiếu checkpoint page {page_no}: {page_path}")
            with page_path.open("r", encoding="utf-8") as src:
                for line in src:
                    if line.strip(): out.write(line); count += 1
        out.flush(); os.fsync(out.fileno())
    os.replace(tmp, raw_path); return count

def fetch_invoices(client: httpx.Client, type_code: str, fd: str, td: str, unl: int, page_size: int,
                   max_retries: int = 3, retry_delay: float = 2.0, sleep_func=time.sleep,
                   raw_path: Path | None = None, resume: bool = False, adaptive_page_size: bool = True,
                   min_page_size: int = 10, workers: int = 1, accumulate: bool = True) -> list[dict[str, Any]]:
    """Fetch with bounded concurrency. Production uses ``accumulate=False``."""
    # Compatibility path for in-memory callers and old .json checkpoints.
    if raw_path is None or raw_path.suffix != ".jsonl":
        rows: list[dict[str, Any]] = _prepare_raw_checkpoint(raw_path, resume) if raw_path else []
        start = len(rows); current = page_size
        while True:
            try: batch = _fetch_page(client, type_code, fd, td, unl, start, current, max_retries, retry_delay, sleep_func)
            except httpx.HTTPStatusError as exc:
                if adaptive_page_size and exc.response.status_code in (502, 504) and current > min_page_size:
                    current = _next_smaller_page_size(current, min_page_size); continue
                raise
            eprint(f"[fetch] {type_code} page={start // current + 1} start={start} got={len(batch)}"); rows.extend(batch)
            if raw_path is not None: _append_raw_rows(raw_path, batch)
            if len(batch) < current: return rows
            start += current

    raw_path.parent.mkdir(parents=True, exist_ok=True); pages_dir = _page_dir(raw_path); manifest_path = pages_dir / "manifest.json"
    if not resume:
        raw_path.unlink(missing_ok=True)
        if pages_dir.exists():
            for old in pages_dir.glob("*"): old.unlink(missing_ok=True)
    pages_dir.mkdir(parents=True, exist_ok=True)
    if resume and raw_path.exists() and not manifest_path.exists():
        old = _read_raw_rows(raw_path); eprint(f"[resume] legacy/raw checkpoint rows={len(old)}")
        return old if accumulate else []
    if resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")); expected = {"type": type_code, "fd": fd, "td": td, "page_size": page_size}
        if any(manifest.get(k) != v for k, v in expected.items()): raise ValueError(f"Checkpoint không khớp tham số hiện tại: {manifest_path}")
        if manifest.get("complete") and raw_path.exists():
            eprint(f"[resume] {type_code} complete rows={manifest.get('rows', 0)}"); return _read_raw_rows(raw_path) if accumulate else []
    else:
        manifest = {"version": 1, "type": type_code, "fd": fd, "td": td, "page_size": page_size, "complete": False}; _atomic_json(manifest_path, manifest)
    completed = {int(p.stem) for p in pages_dir.glob("[0-9]*.jsonl")}; worker_count = max(1, int(workers)); eprint(f"[workers] parallel pages={worker_count}")
    page_base = 0; last_page = None
    try:
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="fpt-page") as pool:
            while last_page is None:
                page_numbers = list(range(page_base, page_base + worker_count)); futures = {}; batches = {}
                for page_no in page_numbers:
                    page_path = pages_dir / f"{page_no:09d}.jsonl"
                    if page_no in completed: batches[page_no] = _read_raw_rows(page_path)
                    else: futures[pool.submit(_fetch_page, client, type_code, fd, td, unl, page_no * page_size, page_size, max_retries, retry_delay, sleep_func)] = page_no
                for future in as_completed(futures):
                    page_no = futures[future]; batch = future.result(); _write_page(pages_dir / f"{page_no:09d}.jsonl", batch); completed.add(page_no); batches[page_no] = batch
                    eprint(f"[fetch] {type_code} page={page_no + 1} start={page_no * page_size} got={len(batch)}")
                for page_no in page_numbers:
                    if len(batches[page_no]) < page_size:
                        last_page = page_no
                        for extra in list(completed):
                            if extra > last_page: (pages_dir / f"{extra:09d}.jsonl").unlink(missing_ok=True)
                        break
                page_base += worker_count
    except KeyboardInterrupt:
        eprint(f"[checkpoint] interruption; completed pages={len(completed)}"); raise
    total = _assemble_pages(raw_path, pages_dir, int(last_page)); manifest.update({"complete": True, "last_page": last_page, "rows": total}); _atomic_json(manifest_path, manifest)
    eprint(f"[done] {type_code} rows={total}"); return _read_raw_rows(raw_path) if accumulate else []

def checkpoint_info(raw_path: Path) -> dict[str, Any]:
    manifest = _page_dir(raw_path) / "manifest.json"
    return json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}

def build_client(token: str) -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=120, follow_redirects=True, headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0 Chrome/146.0.0.0 Safari/537.36", "Content-Type": "application/json"})
