import json
import time
from pathlib import Path
from typing import Any, Iterable

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .constants import (
    CONVERTED_INV_LABELS,
    INVOICE_STATUS_LABELS,
    KNOWN_TYPE_LABELS,
    MAIL_STATUS_LABELS,
    MINUTES_SIGN_STATUS_LABELS,
    STATUS_RECEIVED_LABELS,
    UI_EXPORT_COLUMNS,
)
from .formatting import display_date, display_number, localize_iso, lookup_label
from .log import eprint

EXCEL_MAX_ROWS = 1_048_576
EXCEL_MAX_DATA_ROWS = EXCEL_MAX_ROWS - 1


def resolve_ou_display(row: dict[str, Any]) -> Any:
    if row.get("ou_display") not in (None, ""):
        return row.get("ou_display")
    if row.get("sname") not in (None, ""):
        return row.get("sname")
    org = row.get("org")
    if isinstance(org, dict) and org.get("on"):
        return org.get("on")
    return row.get("ou", "")


def resolve_business_class(row: dict[str, Any]) -> Any:
    if row.get("business_class") not in (None, ""):
        return row.get("business_class")
    raw_class = row.get("class")
    if raw_class in (None, "", 0, "0"):
        return ""
    return raw_class


def resolve_dtl_invs_status(row: dict[str, Any]) -> Any:
    if row.get("dtl_invs_status") not in (None, ""):
        return row.get("dtl_invs_status")
    if not row.get("sec_dtl"):
        return ""
    if row.get("is_lock") in (1, "1", True):
        return "Chưa xử lý"
    return "Đã xử lý"


def resolve_cancel_date(row: dict[str, Any]) -> str:
    cancel_date = row.get("canrdt") or row.get("endtime")
    cde = str(row.get("cde") or "")
    if str(row.get("status")) == "4" and row.get("cid") and "Bị thay thế" in cde:
        cancel_date = ""
    return display_date(cancel_date)


def build_ui_export_row(row: dict[str, Any]) -> dict[str, Any]:
    values = {
        "inc": row.get("inc", ""),
        "idt": display_date(row.get("idt")),
        "form": row.get("form", ""),
        "serial": row.get("serial", ""),
        "seq": row.get("seq", ""),
        "status": lookup_label(row.get("status"), INVOICE_STATUS_LABELS),
        "status_received": lookup_label(row.get("status_received"), STATUS_RECEIVED_LABELS),
        "ma_cqthu": row.get("ma_cqthu", ""),
        "btax": row.get("btax", "") or "",
        "bname": row.get("bname", "") or "",
        "buyer": row.get("buyer", "") or "",
        "baddr": row.get("baddr", "") or "",
        "btel": row.get("btel", "") or "",
        "idnumber": row.get("idnumber") or row.get("passport_number") or "",
        "sum": display_number(row.get("sum")),
        "vat": display_number(row.get("vat")),
        "total": display_number(row.get("total")),
        "curr": row.get("curr", "") or "",
        "exrt": display_number(row.get("exrt")),
        "sec": row.get("sec", "") or "",
        "bmail": row.get("bmail", "") or "",
        "ou": resolve_ou_display(row),
        "uc": row.get("uc", "") or "",
        "ic": row.get("ic", "") or "",
        "adjdes": row.get("adjdes", "") or "",
        "cde": row.get("cde", "") or "",
        "business_class": resolve_business_class(row),
        "dtl_invs_status": resolve_dtl_invs_status(row),
        "sec_dtl": row.get("sec_dtl", "") or "",
        "canrdt": resolve_cancel_date(row),
        "canref": row.get("canref", "") or "",
        "canrea": row.get("canrea", "") or "",
        "adjrdt": display_date(row.get("adjrdt")),
        "adjref": row.get("adjref", "") or "",
        "adjrea": row.get("adjrea", "") or "",
        "minutes_status_sign": lookup_label(
            "null" if row.get("minutes_status_sign") is None else row.get("minutes_status_sign"),
            MINUTES_SIGN_STATUS_LABELS,
        ),
        "code_minutes_sign": row.get("code_minutes_sign", "") or "",
        "bcode": row.get("bcode", "") or "",
        "note": row.get("note", "") or "",
        "maildt": lookup_label(row.get("maildt"), MAIL_STATUS_LABELS),
        "converted_inv": lookup_label(row.get("converted_inv"), CONVERTED_INV_LABELS),
        "id_batch": row.get("id_batch", "") or "",
        "dt": display_date(row.get("dt")),
    }
    return {header: values.get(field_id, "") for field_id, header in UI_EXPORT_COLUMNS}


def normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return value


def flatten_invoice(row: dict[str, Any], type_label: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        out[key] = normalize_value(value)
    out["type_label"] = type_label
    out["idt_local"] = localize_iso(row.get("idt"))
    return out


def sheet_name_for_type(code: str, label: str) -> str:
    base = f"{code} {label}".replace("/", "-")
    bad = set('[]:*?/\\')
    cleaned = "".join("-" if c in bad else c for c in base)
    return cleaned[:31]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def autosize_columns(ws) -> None:
    for column_cells in ws.columns:
        length = 0
        col = column_cells[0].column_letter
        for cell in column_cells:
            val = "" if cell.value is None else str(cell.value)
            if len(val) > length:
                length = len(val)
        ws.column_dimensions[col].width = min(max(length + 2, 10), 40)


def write_sheet(ws, rows: Iterable[dict[str, Any]], columns: list[str]) -> None:
    ws.append(columns)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    widths = [len(str(column)) for column in columns]

    for row in rows:
        values = [row.get(col, "") for col in columns]
        ws.append(values)

        for index, value in enumerate(values):
            length = len("" if value is None else str(value))
            if length > widths[index]:
                widths[index] = length

    for index, length in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = min(
            max(length + 2, 10),
            40,
        )

    ws.freeze_panes = "A2"


def _sort_invoice_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(row: dict[str, Any]) -> tuple[str, int]:
        raw_inc = row.get("inc")
        try:
            inc_value = int(raw_inc)
        except (TypeError, ValueError):
            inc_value = -1
        return (str(row.get("idt") or ""), inc_value)

    return sorted(rows, key=sort_key, reverse=True)


def _iter_checkpoint_rows(path: Path):
    # Stream invoice objects from JSONL; support legacy JSON array checkpoints.
    if path.suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Raw JSONL không hợp lệ: {path}:{line_no}") from exc
                if not isinstance(row, dict):
                    raise ValueError(f"Raw JSONL phải chứa object hóa đơn: {path}:{line_no}")
                yield row
        return

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Raw JSON phải là list hóa đơn: {path}")
    yield from payload


def iter_checkpoint_rows(path: Path):
    """Public streaming reader for JSONL and legacy JSON array checkpoints."""
    yield from _iter_checkpoint_rows(path)


def _append_write_only_header(ws, values: list[str]) -> None:
    cells = []
    for value in values:
        cell = WriteOnlyCell(ws, value=value)
        cell.font = Font(bold=True)
        cells.append(cell)
    ws.append(cells)


def _raw_path_for_type(raw_dir: Path, type_code: str) -> Path | None:
    safe_code = type_code.replace("/", "_")
    jsonl = raw_dir / f"{safe_code}.jsonl"
    if jsonl.exists():
        return jsonl
    legacy_json = raw_dir / f"{safe_code}.json"
    if legacy_json.exists():
        return legacy_json
    return None


def export_workbook(
    output_xlsx: Path,
    all_rows: list[dict[str, Any]],
    by_type: dict[str, list[dict[str, Any]]],
    metadata: dict[str, Any],
) -> None:
    # FAST exporter: raw JSONL -> build_ui_export_row -> write_only XLSX.
    started = time.perf_counter()
    raw_dir = output_xlsx.parent / "raw"

    requested_types = list(metadata.get("types") or [])
    counts = dict(metadata.get("counts") or {})
    total_rows = int(metadata.get("total_rows") or 0)

    raw_paths: list[tuple[str, Path]] = []
    if raw_dir.exists():
        for type_code in requested_types:
            raw_path = _raw_path_for_type(raw_dir, type_code)
            if raw_path is not None:
                raw_paths.append((type_code, raw_path))
        if not requested_types and not raw_paths:
            for raw_path in sorted(raw_dir.glob("*.jsonl")):
                type_code = raw_path.stem
                if type_code == "01_MTT":
                    type_code = "01/MTT"
                raw_paths.append((type_code, raw_path))

    use_raw_stream = bool(raw_paths)

    if use_raw_stream:
        all_rows.clear()
        by_type.clear()

    wb = Workbook(write_only=True)

    ws_meta = wb.create_sheet("metadata")
    ws_meta.freeze_panes = "A2"
    _append_write_only_header(ws_meta, ["key", "value"])
    for key, value in metadata.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        ws_meta.append([key, value])

    ws_summary = wb.create_sheet("summary")
    ws_summary.freeze_panes = "A2"
    _append_write_only_header(ws_summary, ["type_code", "type_label", "count"])
    if requested_types:
        for code in requested_types:
            ws_summary.append([code, KNOWN_TYPE_LABELS.get(code, code), counts.get(code, 0)])
    else:
        for code, count in counts.items():
            ws_summary.append([code, KNOWN_TYPE_LABELS.get(code, code), count])
    ws_summary.append(["TOTAL", "Tất cả", total_rows])

    ws_all = wb.create_sheet("invoices_all")
    ws_all.freeze_panes = "A2"
    ui_headers = [header for _, header in UI_EXPORT_COLUMNS]
    _append_write_only_header(ws_all, ui_headers)

    written = 0

    if use_raw_stream:
        eprint(f"[excel] FAST write_only raw={raw_dir} expected_rows={total_rows}")
        for type_code, raw_path in raw_paths:
            file_rows = 0
            file_started = time.perf_counter()
            eprint(f"[excel] read {type_code} <- {raw_path.name}")
            for raw_row in _iter_checkpoint_rows(raw_path):
                ui_row = build_ui_export_row(raw_row)
                ws_all.append([ui_row.get(header, "") for header in ui_headers])
                written += 1
                file_rows += 1
                if written % 10000 == 0:
                    elapsed = time.perf_counter() - started
                    rate = written / elapsed if elapsed else 0
                    eprint(f"[excel] rows={written:,} elapsed={elapsed:.1f}s rate={rate:,.0f} rows/s")
            eprint(f"[excel] done {type_code} rows={file_rows:,} time={time.perf_counter() - file_started:.1f}s")
    else:
        # Fallback giữ tương thích unit test/direct call.
        sorted_all_rows = _sort_invoice_rows(all_rows)
        for row in sorted_all_rows:
            ui_row = build_ui_export_row(row)
            ws_all.append([ui_row.get(header, "") for header in ui_headers])
            written += 1

    output_xlsx.parent.mkdir(parents=True, exist_ok=True)
    before_save = time.perf_counter()
    eprint(f"[excel] stream-done rows={written:,} time={before_save - started:.1f}s")
    wb.save(output_xlsx)
    ended = time.perf_counter()
    eprint(f"[excel] saved rows={written:,} save={ended - before_save:.1f}s total={ended - started:.1f}s file={output_xlsx}")


def export_raw_workbook(output_xlsx: Path, raw_paths: list[tuple[str, Path]], metadata: dict[str, Any],
                        progress_every: int = 10_000) -> int:
    """Production exporter: JSONL -> authoritative UI mapping -> write-only XLSX."""
    total = int(metadata.get("total_rows", 0))
    if total > EXCEL_MAX_DATA_ROWS:
        raise ValueError(f"Excel row limit exceeded: {total} data rows > {EXCEL_MAX_DATA_ROWS}")
    started = time.perf_counter(); wb = Workbook(write_only=True)
    meta = wb.create_sheet("metadata"); _append_write_only_header(meta, ["key", "value"])
    for key, value in metadata.items():
        meta.append([key, json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value])
    summary = wb.create_sheet("summary"); _append_write_only_header(summary, ["type_code", "type_label", "count"])
    counts = metadata.get("counts", {})
    for code in metadata.get("types", list(counts)):
        summary.append([code, KNOWN_TYPE_LABELS.get(code, code), counts.get(code, 0)])
    summary.append(["TOTAL", "Tất cả", total])
    sheet = wb.create_sheet("invoices_all"); headers = [h for _, h in UI_EXPORT_COLUMNS]; _append_write_only_header(sheet, headers)
    written = 0
    for _, path in raw_paths:
        for raw in _iter_checkpoint_rows(path):
            if written >= EXCEL_MAX_DATA_ROWS: raise ValueError("Excel row limit exceeded while streaming")
            row = build_ui_export_row(raw); sheet.append([row.get(h, "") for h in headers]); written += 1
            if progress_every and written % progress_every == 0:
                elapsed = time.perf_counter() - started; eprint(f"[excel] rows={written:,} rate={written / elapsed:,.0f} rows/s")
    if written != total: raise ValueError(f"Raw row count mismatch: metadata={total}, actual={written}")
    output_xlsx.parent.mkdir(parents=True, exist_ok=True); wb.save(output_xlsx)
    eprint(f"[excel] saved rows={written:,} time={time.perf_counter() - started:.1f}s file={output_xlsx}")
    return written
