import argparse
import importlib.util
import json
import sys
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

ENV_TEMPLATE = """FPT_EINVOICE_MST=<YOUR_MST>
FPT_EINVOICE_USERNAME=<YOUR_USERNAME>
FPT_EINVOICE_PASSWORD=<YOUR_PASSWORD>
"""


def positive_int_arg(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("phải là số nguyên") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError("phải lớn hơn 0")
    return value


def non_negative_int_arg(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("phải là số nguyên") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("không được âm")
    return value


def non_negative_float_arg(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("phải là số") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("không được âm")
    return value


def resolve_session_file(args: Any, profile_dir: Path) -> Path:
    return (
        Path(args.session_file).expanduser().resolve()
        if getattr(args, "session_file", None)
        else profile_dir / "fpt_session.json"
    )


def resolve_runtime_paths(args: Any) -> tuple[Path, Path, Path]:
    output_dir = Path(getattr(args, "output_dir", "./output")).expanduser().resolve()
    profile_dir = Path(getattr(args, "profile_dir", "./profiles/default")).expanduser().resolve()
    session_file = resolve_session_file(args, profile_dir)
    return output_dir, profile_dir, session_file


def resolve_output_xlsx(output_dir: Path, output_name: str | None, fd: str, td: str) -> Path:
    if output_name:
        if output_name in {".", ".."} or "/" in output_name or "\\" in output_name:
            raise ValueError("--output-name chỉ được là tên file, không được chứa đường dẫn")
        return output_dir / output_name

    safe_from = fd[:10]
    safe_to = td[:10]
    return output_dir / f"fpt_einvoice_{safe_from}_to_{safe_to}.xlsx"


def validate_export_args(args: Any, fd: str, td: str) -> None:
    if td < fd:
        raise ValueError("--to-date phải cùng ngày hoặc sau --from-date")

    page_size = int(getattr(args, "page_size", 2000))
    min_page_size = int(getattr(args, "min_page_size", 10))
    max_retries = int(getattr(args, "max_retries", 3))
    retry_delay = float(getattr(args, "retry_delay", 2.0))
    login_wait_seconds = int(getattr(args, "login_wait_seconds", 35))

    if page_size <= 0:
        raise ValueError("--page-size phải lớn hơn 0")
    if min_page_size <= 0:
        raise ValueError("--min-page-size phải lớn hơn 0")
    if min_page_size > page_size:
        raise ValueError("--min-page-size không được lớn hơn --page-size")
    if max_retries < 0:
        raise ValueError("--max-retries không được âm")
    if retry_delay < 0:
        raise ValueError("--retry-delay không được âm")
    if login_wait_seconds <= 0:
        raise ValueError("--login-wait-seconds phải lớn hơn 0")


def run_init(args: Any) -> dict[str, Any]:
    env_path = Path(args.env_file).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    profile_dir = Path(args.profile_dir).expanduser()

    env_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    created_env = False
    if args.force or not env_path.exists():
        env_path.write_text(ENV_TEMPLATE, encoding="utf-8")
        created_env = True
        try:
            env_path.chmod(0o600)
        except OSError:
            pass

    return {
        "ok": True,
        "created_env": created_env,
        "env_file": str(env_path),
        "profile_dir": str(profile_dir),
        "output_dir": str(output_dir),
        "next": [
            "Sửa file .env với thông tin đăng nhập FPT eInvoice.",
            "Chạy: fpt-einvoice-exporter doctor",
            "Chạy: fpt-einvoice-exporter login --headed",
        ],
    }


def _doctor_check(name: str, ok: bool, message: str, hint: str = "") -> dict[str, Any]:
    check = {"name": name, "ok": ok, "message": message}
    if hint:
        check["hint"] = hint
    return check


def run_doctor(args: Any) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(
        _doctor_check(
            "python",
            sys.version_info >= (3, 9),
            f"Python {sys.version_info.major}.{sys.version_info.minor}",
            "Cài Python 3.9+.",
        )
    )

    missing_deps = [
        module
        for module in ("cloakbrowser", "httpx", "openpyxl")
        if importlib.util.find_spec(module) is None
    ]
    checks.append(
        _doctor_check(
            "dependencies",
            not missing_deps,
            "Đã cài dependency." if not missing_deps else "Thiếu dependency: " + ", ".join(missing_deps),
            "Chạy: pip install .",
        )
    )

    try:
        resolve_login_inputs(args, load_login_env(args.env_file))
        credentials_ok = True
    except ValueError:
        credentials_ok = False
    checks.append(
        _doctor_check(
            "credentials",
            credentials_ok,
            "Đã có đủ thông tin đăng nhập." if credentials_ok else "Thiếu thông tin đăng nhập trong .env hoặc env vars.",
            "Chạy: fpt-einvoice-exporter init rồi sửa file .env.",
        )
    )

    output_dir, profile_dir, session_file = resolve_runtime_paths(args)
    for name, path in (("output_dir", output_dir), ("profile_dir", profile_dir)):
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = path.is_dir()
        except OSError:
            writable = False
        checks.append(
            _doctor_check(
                name,
                writable,
                "Có thể ghi thư mục runtime." if writable else "Không thể ghi thư mục runtime.",
                f"Kiểm tra quyền ghi: {path}",
            )
        )

    checks.append(
        _doctor_check(
            "session_cache",
            session_file.exists(),
            "Đã có session cache." if session_file.exists() else "Chưa có session cache.",
            "Chạy: fpt-einvoice-exporter login --headed",
        )
    )

    return {"ok": all(check["ok"] for check in checks[:-1]), "checks": checks}


def run_login(args: Any) -> dict[str, Any]:
    login_values = resolve_login_inputs(args, load_login_env(args.env_file))
    _, profile_dir, session_file = resolve_runtime_paths(args)

    login = portal_login(
        mst=login_values["mst"],
        username=login_values["username"],
        password=login_values["password"],
        profile_dir=profile_dir,
        headless=not args.headed,
        login_wait_seconds=args.login_wait_seconds,
    )
    context = login["context"]
    try:
        session = login["session"]
        write_session_cache(session_file, session)
        return {
            "ok": True,
            "session_file": str(session_file),
            "types": resolve_types("session", session),
            "next": "Chạy export với: fpt-einvoice-exporter export --from-date YYYY-MM-DD --to-date YYYY-MM-DD",
        }
    finally:
        try:
            context.close()
        except Exception:
            pass


def run_types(args: Any) -> dict[str, Any]:
    login_values = resolve_login_inputs(args, load_login_env(args.env_file))
    _, profile_dir, session_file = resolve_runtime_paths(args)
    session = read_session_cache(session_file, login_values["mst"], login_values["username"])
    if not session:
        raise RuntimeError("Chưa có session cache hợp lệ. Chạy: fpt-einvoice-exporter login --headed")
    return {"ok": True, "types": resolve_types(args.types, session)}


def run_export(args: Any) -> dict[str, Any]:
    login_values = resolve_login_inputs(args, load_login_env(args.env_file))

    fd = parse_date(args.from_date, end_of_day=False)
    td = parse_date(args.to_date, end_of_day=True)
    validate_export_args(args, fd, td)

    output_dir, profile_dir, session_file = resolve_runtime_paths(args)
    raw_dir = output_dir / "raw"
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    output_xlsx = resolve_output_xlsx(output_dir, args.output_name, fd, td)

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
                        adaptive_page_size=getattr(args, "adaptive_page_size", True),
                        min_page_size=getattr(args, "min_page_size", 10),
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

        warnings = []
        if errors:
            warnings.append(
                "Export chỉ hoàn tất một phần. Không dùng workbook này làm kết quả cuối nếu còn lỗi; "
                "chạy lại cùng tham số với --resume sau khi API ổn định."
            )

        metadata = {
            "mst": login_values["mst"],
            "username": login_values["username"],
            "from_date": fd,
            "to_date": td,
            "types": requested_types,
            "counts": {code: len(rows) for code, rows in by_type.items()},
            "errors": errors,
            "warnings": warnings,
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
            "warnings": warnings,
            "total_rows": metadata["total_rows"],
        }
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass


def add_login_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--mst", help="Mã số thuế đăng nhập; fallback FPT_EINVOICE_MST")
    parser.add_argument("--username", help="Username đăng nhập; fallback FPT_EINVOICE_USERNAME")
    parser.add_argument("--password", help="Mật khẩu đăng nhập; fallback FPT_EINVOICE_PASSWORD")
    parser.add_argument("--env-file", default=".env", help="File .env chứa credential; mặc định ./.env")


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile-dir", default="./profiles/default")
    parser.add_argument("--output-dir", default="./output")
    parser.add_argument(
        "--session-file",
        default=None,
        help="File cache session/token; mặc định <profile-dir>/fpt_session.json",
    )


def add_export_args(parser: argparse.ArgumentParser, required_dates: bool) -> None:
    add_login_args(parser)
    parser.add_argument("--from-date", required=required_dates, help="YYYY-MM-DD hoặc DD/MM/YYYY")
    parser.add_argument("--to-date", required=required_dates, help="YYYY-MM-DD hoặc DD/MM/YYYY")
    parser.add_argument("--types", default="all-known", help="session | all-known | CSV mã loại HĐ")
    parser.add_argument("--unl", type=int, default=2)
    parser.add_argument("--page-size", type=positive_int_arg, default=2000)
    parser.add_argument(
        "--min-page-size",
        type=positive_int_arg,
        default=10,
        help="Page size nhỏ nhất khi tự giảm do API 502/504",
    )
    parser.add_argument(
        "--max-retries",
        type=non_negative_int_arg,
        default=3,
        help="Số lần retry cho lỗi API transient 429/5xx",
    )
    parser.add_argument(
        "--retry-delay",
        type=non_negative_float_arg,
        default=2.0,
        help="Số giây chờ giữa các lần retry API",
    )
    parser.add_argument(
        "--no-adaptive-page-size",
        dest="adaptive_page_size",
        action="store_false",
        default=True,
        help="Tắt tự giảm page size khi API trả 502/504",
    )
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
        type=positive_int_arg,
        default=35,
        help="Số giây chờ nút Đăng nhập sẵn sàng; tăng khi cần tick reCAPTCHA thủ công với --headed",
    )
    parser.add_argument("--session-file", default=None, help="File cache session/token; mặc định <profile-dir>/fpt_session.json")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export danh sách hóa đơn FPT.eInvoice ra Excel bằng CloakBrowser + API")
    add_export_args(parser, required_dates=False)
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", help="Tạo .env mẫu và thư mục runtime")
    init_parser.add_argument("--env-file", default=".env", help="File .env sẽ tạo; mặc định ./.env")
    init_parser.add_argument("--profile-dir", default="./profiles/default")
    init_parser.add_argument("--output-dir", default="./output")
    init_parser.add_argument("--force", action="store_true", help="Ghi đè .env nếu đã tồn tại")

    doctor_parser = subparsers.add_parser("doctor", help="Kiểm tra môi trường trước khi export")
    add_login_args(doctor_parser)
    add_runtime_args(doctor_parser)

    login_parser = subparsers.add_parser("login", help="Đăng nhập và lưu session cache")
    add_login_args(login_parser)
    login_parser.add_argument("--profile-dir", default="./profiles/default")
    login_parser.add_argument("--session-file", default=None, help="File cache session/token; mặc định <profile-dir>/fpt_session.json")
    login_parser.add_argument("--headed", action="store_true", help="Mở browser có giao diện")
    login_parser.add_argument(
        "--login-wait-seconds",
        type=positive_int_arg,
        default=300,
        help="Số giây chờ nút Đăng nhập sẵn sàng",
    )

    types_parser = subparsers.add_parser("types", help="In danh sách loại hóa đơn từ session cache")
    add_login_args(types_parser)
    types_parser.add_argument("--profile-dir", default="./profiles/default")
    types_parser.add_argument("--session-file", default=None, help="File cache session/token; mặc định <profile-dir>/fpt_session.json")
    types_parser.add_argument("--types", default="session", help="session | all-known | CSV mã loại HĐ")

    export_parser = subparsers.add_parser("export", help="Export hóa đơn ra Excel")
    add_export_args(export_parser, required_dates=True)
    return parser


def run_command(args: Any, parser: argparse.ArgumentParser) -> tuple[dict[str, Any], int]:
    if args.command == "init":
        return run_init(args), 0
    if args.command == "doctor":
        result = run_doctor(args)
        return result, 0 if result["ok"] else 1
    if args.command == "login":
        return run_login(args), 0
    if args.command == "types":
        return run_types(args), 0

    if not args.from_date or not args.to_date:
        parser.error("export cần --from-date và --to-date")
    result = run_export(args)
    return result, 0 if result.get("ok", True) else 3


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        result, exit_code = run_command(args, parser)
    except KeyboardInterrupt:
        eprint(
            "Đã dừng theo Ctrl+C. Raw JSON đã checkpoint sau mỗi page thành công; "
            "chạy lại cùng tham số và thêm --resume để tiếp tục."
        )
        return 130
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code
