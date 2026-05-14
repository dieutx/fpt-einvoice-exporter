import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fpt_einvoice_exporter as mod


class EnvSupportTests(unittest.TestCase):
    def test_parse_env_file_reads_supported_keys_and_strips_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "# comment\n"
                "FPT_EINVOICE_MST=0100123456\n"
                "FPT_EINVOICE_USERNAME='demo_user'\n"
                'FPT_EINVOICE_PASSWORD="demo-pass"\n'
                "IGNORED_KEY=ignored\n",
                encoding="utf-8",
            )

            values = mod.parse_env_file(env_path)

            self.assertEqual(values["FPT_EINVOICE_MST"], "0100123456")
            self.assertEqual(values["FPT_EINVOICE_USERNAME"], "demo_user")
            self.assertEqual(values["FPT_EINVOICE_PASSWORD"], "demo-pass")
            self.assertNotIn("IGNORED_KEY", values)

    def test_parse_env_file_strips_inline_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "FPT_EINVOICE_MST=0100123456 # note\n"
                "FPT_EINVOICE_USERNAME='demo_user' # comment\n"
                'FPT_EINVOICE_PASSWORD="demo-pass" # trailing\n',
                encoding="utf-8",
            )

            values = mod.parse_env_file(env_path)

            self.assertEqual(values["FPT_EINVOICE_MST"], "0100123456")
            self.assertEqual(values["FPT_EINVOICE_USERNAME"], "demo_user")
            self.assertEqual(values["FPT_EINVOICE_PASSWORD"], "demo-pass")

    def test_resolve_login_inputs_falls_back_to_env_values(self):
        class Args:
            mst = None
            username = None
            password = None

        resolved = mod.resolve_login_inputs(
            Args(),
            {
                "FPT_EINVOICE_MST": "0100123456",
                "FPT_EINVOICE_USERNAME": "demo_user",
                "FPT_EINVOICE_PASSWORD": "demo-pass",
            },
        )

        self.assertEqual(
            resolved,
            {
                "mst": "0100123456",
                "username": "demo_user",
                "password": "demo-pass",
            },
        )

    def test_cli_values_override_env_values(self):
        class Args:
            mst = "cli-mst"
            username = "cli-user"
            password = "cli-pass"

        resolved = mod.resolve_login_inputs(
            Args(),
            {
                "FPT_EINVOICE_MST": "env-mst",
                "FPT_EINVOICE_USERNAME": "env-user",
                "FPT_EINVOICE_PASSWORD": "env-pass",
            },
        )

        self.assertEqual(
            resolved,
            {
                "mst": "cli-mst",
                "username": "cli-user",
                "password": "cli-pass",
            },
        )

    def test_resolve_login_inputs_raises_when_missing_required_values(self):
        class Args:
            mst = None
            username = "demo_user"
            password = None

        with self.assertRaisesRegex(ValueError, r"mst,password"):
            mod.resolve_login_inputs(Args(), {})

    def test_resolve_login_inputs_rejects_whitespace_only_cli_values(self):
        class Args:
            mst = "   "
            username = "demo_user"
            password = "demo-pass"

        with self.assertRaisesRegex(ValueError, r"mst"):
            mod.resolve_login_inputs(Args(), {})

    def test_resolve_login_inputs_rejects_whitespace_only_env_values(self):
        class Args:
            mst = None
            username = None
            password = None

        with self.assertRaisesRegex(ValueError, r"mst"):
            mod.resolve_login_inputs(
                Args(),
                {
                    "FPT_EINVOICE_MST": "   ",
                    "FPT_EINVOICE_USERNAME": "demo_user",
                    "FPT_EINVOICE_PASSWORD": "demo-pass",
                },
            )

    def test_cli_missing_credentials_exits_cleanly_without_traceback(self):
        repo_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            missing_env_file = Path(tmp) / "missing.env"
            env = dict(os.environ)
            env.pop("FPT_EINVOICE_MST", None)
            env.pop("FPT_EINVOICE_USERNAME", None)
            env.pop("FPT_EINVOICE_PASSWORD", None)
            result = subprocess.run(
                [
                    sys.executable,
                    "fpt_einvoice_exporter.py",
                    "--env-file",
                    str(missing_env_file),
                    "--from-date",
                    "2026-05-01",
                    "--to-date",
                    "2026-05-12",
                ],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                env=env,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Thiếu thông tin đăng nhập bắt buộc", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
