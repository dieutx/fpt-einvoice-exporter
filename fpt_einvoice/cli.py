import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .api import build_client, fetch_invoices, resolve_types
from .auth import portal_login
from .config import load_login_env, resolve_login_inputs
from .constants import KNOWN_TYPE_LABELS
from .export import export_workbook, flatten_invoice, write_json
from .formatting import parse_date
from .log import eprint


def run_export(args: Any) -> dict[str, Any]:
    login_values = resolve_login_inputs(args, load_login_env(args.env_file))

    fd = parse_date(args.from_date, end_of_day=False)
    td = parse_date(args.to_date, end_of_day=True)

    output_dir = Path(args.output_dir).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve()
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    if args.output_name:
        output_xlsx = output_dir / args.output_name
    else:
        safe_from = fd[:10]
        safe_to = td[:10]
        output_xlsx = output_dir / f"fpt_einvoice_{safe_from}_to_{safe_to}.xlsx"

    login = portal_login(
        mst=login_values["mst"],
        username=login_values["username"],
        password=login_values["password"],
        profile_dir=profile_dir,
        headless=not args.headed,
    )
    context = login["context"]
    session = login["session"]
    token = login["token"]

    try:
        requested_types = resolve_types(args.types, session)
        eprint("[types]", requested_types)

        all_rows: list[dict[str, Any]] = []
        by_type: dict[str, list[dict[str, Any]]] = {}

        client = build_client(token)
        try:
            for type_code in requested_types:
                rows = fetch_invoices(client, type_code, fd, td, args.unl, args.page_size)
                write_json(raw_dir / f"{type_code.replace('/', '_')}.json", rows)
                label = KNOWN_TYPE_LABELS.get(type_code, type_code)
                flat_rows = [flatten_invoice(row, label) for row in rows]
                by_type[type_code] = flat_rows
                all_rows.extend(flat_rows)
        finally:
            client.close()

        metadata = {
            "mst": login_values["mst"],
            "username": login_values["username"],
            "from_date": fd,
            "to_date": td,
            "types": requested_types,
            "counts": {code: len(rows) for code, rows in by_type.items()},
            "total_rows": len(all_rows),
            "profile_dir": str(profile_dir),
            "session_uid": session.get("uid"),
            "session_fn": session.get("fn"),
            "session_ou": session.get("ou"),
            "generated_at": datetime.now().astimezone().isoformat(),
        }
        write_json(output_dir / "metadata.json", metadata)
        export_workbook(output_xlsx, all_rows, by_type, metadata)

        return {
            "ok": True,
            "output_xlsx": str(output_xlsx),
            "output_dir": str(output_dir),
            "metadata_json": str(output_dir / "metadata.json"),
            "counts": metadata["counts"],
            "total_rows": metadata["total_rows"],
        }
    finally:
        try:
            context.close()
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export danh sách hóa đơn FPT.eInvoice ra Excel bằng CloakBrowser + API")
    parser.add_argument("--mst", help="Mã số thuế đăng nhập; fallback FPT_EINVOICE_MST")
    parser.add_argument("--username", help="Username đăng nhập; fallback FPT_EINVOICE_USERNAME")
    parser.add_argument("--password", help="Mật khẩu đăng nhập; fallback FPT_EINVOICE_PASSWORD")
    parser.add_argument("--env-file", default=".env", help="File .env chứa credential; mặc định ./.env")
    parser.add_argument("--from-date", required=True, help="YYYY-MM-DD hoặc DD/MM/YYYY")
    parser.add_argument("--to-date", required=True, help="YYYY-MM-DD hoặc DD/MM/YYYY")
    parser.add_argument("--types", default="all-known", help="session | all-known | CSV mã loại HĐ")
    parser.add_argument("--unl", type=int, default=2)
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--profile-dir", default="./profiles/default")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--headed", action="store_true", help="Mở browser có giao diện")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = run_export(args)
    except ValueError as exc:
        parser.error(str(exc))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
