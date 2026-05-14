import os
from pathlib import Path
from typing import Any

from .constants import LOGIN_ENV_MAP


def strip_inline_comment(value: str) -> str:
    out: list[str] = []
    in_single = False
    in_double = False

    for index, char in enumerate(value):
        if char == "'" and not in_double:
            in_single = not in_single
            out.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            out.append(char)
            continue
        if char == "#" and not in_single and not in_double:
            prev_char = value[index - 1] if index > 0 else ""
            if index == 0 or prev_char.isspace():
                break
        out.append(char)

    return "".join(out).strip()


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in LOGIN_ENV_MAP.values():
            continue
        value = strip_inline_comment(value)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    return values


def load_login_env(env_file: str | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_file:
        values.update(parse_env_file(Path(env_file).expanduser()))

    for env_key in LOGIN_ENV_MAP.values():
        env_value = os.getenv(env_key)
        if env_value:
            values[env_key] = env_value

    return values


def resolve_login_inputs(args: Any, env_values: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    missing: list[str] = []

    for arg_name, env_key in LOGIN_ENV_MAP.items():
        cli_value = getattr(args, arg_name, None)
        raw_value = cli_value if cli_value not in (None, "") else env_values.get(env_key)
        if raw_value is None:
            missing.append(arg_name)
            continue
        value = str(raw_value).strip()
        if not value or (value.startswith("<YOUR_") and value.endswith(">")):
            missing.append(arg_name)
            continue
        resolved[arg_name] = value

    if missing:
        raise ValueError(
            "Thiếu thông tin đăng nhập bắt buộc: "
            + ",".join(missing)
            + ". Cung cấp qua CLI hoặc file .env / biến môi trường."
        )

    return resolved
