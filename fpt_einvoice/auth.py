import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from cloakbrowser import launch_persistent_context

from .constants import BASE_URL
from .log import eprint


def session_account_matches(session: dict[str, Any], mst: str, username: str) -> bool:
    uid = str(session.get("uid", "")).strip().lower()
    expected_uid = f"{mst}.{username}".strip().lower()
    return bool(uid) and uid == expected_uid


def read_session_cache(path: Path, mst: str, username: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    session = payload.get("session") if isinstance(payload, dict) else None
    if not isinstance(session, dict):
        return None
    if not session.get("token"):
        return None
    if not session_account_matches(session, mst, username):
        return None
    return session


def write_session_cache(path: Path, session: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session": session,
        "cached_at": datetime.now().astimezone().isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def wait_for_session(page: Any, timeout_seconds: int = 35) -> dict[str, Any]:
    end = time.time() + timeout_seconds
    while time.time() < end:
        session_text = page.evaluate("sessionStorage.getItem('session')")
        if session_text:
            try:
                return json.loads(session_text)
            except json.JSONDecodeError:
                pass
        page.wait_for_timeout(1000)
    raise RuntimeError("Không lấy được session sau khi đăng nhập")


def wait_for_enabled(locator: Any, timeout_seconds: int) -> None:
    end = time.time() + timeout_seconds
    while time.time() < end:
        try:
            if locator.is_enabled():
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError(
        "Nút đăng nhập chưa sẵn sàng. Nếu trang đang yêu cầu reCAPTCHA, chạy với "
        "--headed --login-wait-seconds 300 rồi tick captcha thủ công."
    )


def portal_login(
    mst: str,
    username: str,
    password: str,
    profile_dir: Path,
    headless: bool,
    login_wait_seconds: int = 35,
) -> dict[str, Any]:
    profile_dir.mkdir(parents=True, exist_ok=True)
    context = launch_persistent_context(
        profile_dir,
        headless=headless,
        humanize=True,
        locale="vi-VN",
        timezone="Asia/Ho_Chi_Minh",
    )
    page = context.pages[0] if context.pages else context.new_page()
    try:
        page.goto(BASE_URL + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)

        session_text = page.evaluate("sessionStorage.getItem('session')")
        if not session_text:
            eprint("[login] Chưa có session, tiến hành đăng nhập...")
            page.get_by_placeholder("MST").fill(mst)
            page.get_by_placeholder("Tài khoản").fill(username)
            page.get_by_placeholder("Mật khẩu").fill(password)
            login_button = page.get_by_role("button", name=re.compile("Đăng nhập"))
            wait_for_enabled(login_button, login_wait_seconds)
            login_button.click(timeout=15000)
            session = wait_for_session(page)
        else:
            eprint("[login] Dùng session có sẵn trong profile")
            session = json.loads(session_text)

        token = session.get("token")
        if not token:
            raise RuntimeError("Session không chứa bearer token")

        return {
            "context": context,
            "page": page,
            "session": session,
            "token": token,
        }
    except Exception:
        try:
            context.close()
        except Exception:
            pass
        raise
