import json
import re
import time
from pathlib import Path
from typing import Any

from cloakbrowser import launch_persistent_context

from .constants import BASE_URL
from .log import eprint


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


def portal_login(mst: str, username: str, password: str, profile_dir: Path, headless: bool) -> dict[str, Any]:
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
            page.get_by_role("button", name=re.compile("Đăng nhập")).click(timeout=15000)
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
