import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from .api import build_client, fetch_invoices, resolve_types
from .auth import delete_session_cache, portal_login, read_session_cache, write_session_cache
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
    session_file = (
        Path(args.session_file).expanduser().resolve()
        if args.session_file
        else profile_dir / "fpt_session.json"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    if args.output_name:
        output_xlsx = output_dir / args.output_name
    else:
        safe_from = fd[:10]
        safe_to = td[:10]
        output_xlsx = output_dir / f"fpt_einvoice_{safe_from}_to_{safe_to}.xlsx"

    context = None
    session = None
    used_cached_session = False
    if args.reuse_token:
        session = read_session_cache(session_file, login_values["mst"], login_values["username"])
        if session:
            used_cached_session = True
            eprint(f"[login] Dùng bearer token cache: {session_file}")

    if session:
        token = session["token"]
    else:
        login = portal_login(
            mst=login_values["mst"],
            username=login_values["username"],
            password=login_values["password"],
            profile_dir=profile_dir,
            headless=not args.headed,
            login_wait_seconds=args.login_wait_seconds,
        )
        context = login["context"]
        session = login["session"]
        token = login["token"]
        if args.reuse_token:
            write_session_cache(session_file, session)
            eprint(f"[login] Đã lưu bearer token cache: {session_file}")

    try:
        requested_types = resolve_types(args.types, session)
        eprint("[types]", requested_types)

        all_rows: list[dict[str, Any]] = []
        by_type: dict[str, list[dict[str, Any]]] = {}
        errors: dict[str, dict[str, str]] = {}

        client = build_client(token)
        try:
            for type_code in requested_types:
                raw_path = raw_dir / f"{type_code.replace('/', '_')}.json"
                try:
                    rows = fetch_invoices(
                        client,
                        type_code,
                        fd,
                        td,
                        args.unl,
                        args.page_size,
                        max_retries=getattr(args, "max_retries", 3),
                        retry_delay=getattr(args, "retry_delay", 2.0),
                        raw_path=raw_path,
                        resume=getattr(args, "resume", False),
                    )
                    write_json(raw_path, rows)
                except httpx.HTTPStatusError as exc:
                    if used_cached_session and exc.response.status_code in (401, 403):
                        delete_session_cache(session_file)
                        raise RuntimeError(
                            "Token cache hết hạn hoặc không còn quyền truy cập. "
                            "Đã xóa cache, hãy chạy lại để đăng nhập mới."
                        ) from exc
                    if not getattr(args, "continue_on_error", False):
                        raise
                    errors[type_code] = {
                        "error": exc.__class__.__name__,
                        "message": str(exc),
                    }
                    eprint(f"[error] {type_code}: {exc}")
                    continue
                except Exception as exc:
                    if not getattr(args, "continue_on_error", False):
                        raise
                    errors[type_code] = {
                        "error": exc.__class__.__name__,
                        "message": str(exc),
                    }
                    eprint(f"[error] {type_code}: {exc}")
                    continue
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
            "errors": errors,
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
            "ok": not errors,
            "output_xlsx": str(output_xlsx),
            "output_dir": str(output_dir),
            "metadata_json": str(output_dir / "metadata.json"),
            "counts": metadata["counts"],
            "errors": errors,
            "total_rows": metadata["total_rows"],
        }
    finally:
        if context is not None:
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
    parser.add_argument("--max-retries", type=int, default=3, help="Số lần retry cho lỗi API transient 429/5xx")
    parser.add_argument("--retry-delay", type=float, default=2.0, help="Số giây chờ giữa các lần retry API")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Tiếp tục từ raw JSON đã lưu trong output/raw thay vì tải lại các page đã xong",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Nếu một loại hóa đơn lỗi, tiếp tục xuất workbook cho các loại còn lại và ghi lỗi vào metadata",
    )
    parser.add_argument("--profile-dir", default="./profiles/default")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--headed", action="store_true", help="Mở browser có giao diện")
    parser.add_argument(
        "--login-wait-seconds",
        type=int,
        default=35,
        help="Số giây chờ nút Đăng nhập sẵn sàng; tăng khi cần tick reCAPTCHA thủ công với --headed",
    )
    parser.add_argument(
        "--session-file",
        default=None,
        help="File cache session/token; mặc định <profile-dir>/fpt_session.json",
    )
    parser.add_argument(
        "--reuse-token",
        dest="reuse_token",
        action="store_true",
        default=True,
        help="Dùng bearer token cache trước khi mở browser đăng nhập (mặc định)",
    )
    parser.add_argument(
        "--no-reuse-token",
        dest="reuse_token",
        action="store_false",
        help="Bỏ qua token cache và đăng nhập lại bằng browser",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = run_export(args)
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
