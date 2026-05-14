import argparse
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import fpt_einvoice.auth as auth
import fpt_einvoice.cli as cli


class CliCommandTests(unittest.TestCase):
    def test_init_creates_env_template_and_runtime_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = argparse.Namespace(
                env_file=str(tmp_path / ".env"),
                profile_dir=str(tmp_path / "profiles" / "default"),
                output_dir=str(tmp_path / "output"),
                force=False,
            )

            result = cli.run_init(args)

            env_text = (tmp_path / ".env").read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertTrue(result["created_env"])
        self.assertIn("FPT_EINVOICE_MST=<YOUR_MST>", env_text)

    def test_doctor_reports_missing_credentials_without_secret_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                env_file=str(Path(tmp) / ".env"),
                profile_dir=str(Path(tmp) / "profiles" / "default"),
                output_dir=str(Path(tmp) / "output"),
            )

            result = cli.run_doctor(args)

        self.assertFalse(result["ok"])
        self.assertTrue(any(check["name"] == "credentials" and not check["ok"] for check in result["checks"]))
        self.assertNotIn("password", json.dumps(result, ensure_ascii=False).lower())

    def test_doctor_treats_init_placeholders_as_missing_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env_path = tmp_path / ".env"
            env_path.write_text(cli.ENV_TEMPLATE, encoding="utf-8")
            args = argparse.Namespace(
                mst=None,
                username=None,
                password=None,
                env_file=str(env_path),
                profile_dir=str(tmp_path / "profiles" / "default"),
                output_dir=str(tmp_path / "output"),
                session_file=None,
            )

            result = cli.run_doctor(args)

        credentials_check = next(check for check in result["checks"] if check["name"] == "credentials")
        self.assertFalse(credentials_check["ok"])

    def test_login_command_writes_session_cache_without_exporting(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "fresh-token",
            "itype": "01GTKT",
        }

        class FakeContext:
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = argparse.Namespace(
                mst="0123456789",
                username="demo_user",
                password="demo-pass",
                env_file=None,
                profile_dir=str(tmp_path / "profile"),
                session_file=None,
                headed=True,
                login_wait_seconds=300,
            )

            with mock.patch(
                "fpt_einvoice.cli.portal_login",
                return_value={
                    "context": FakeContext(),
                    "page": object(),
                    "session": session,
                    "token": "fresh-token",
                },
            ) as portal_login:
                result = cli.run_login(args)

            cached = auth.read_session_cache(tmp_path / "profile" / "fpt_session.json", "0123456789", "demo_user")

        self.assertTrue(result["ok"])
        self.assertEqual(cached, session)
        portal_login.assert_called_once()
        self.assertTrue(portal_login.call_args.kwargs["headless"] is False)

    def test_types_command_reads_cached_session_types(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "cached-token",
            "itype": "01GTKT,01/MTT",
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args = argparse.Namespace(
                mst="0123456789",
                username="demo_user",
                password="demo-pass",
                env_file=None,
                types="session",
                profile_dir=str(tmp_path / "profile"),
                session_file=None,
            )
            auth.write_session_cache(tmp_path / "profile" / "fpt_session.json", session)

            result = cli.run_types(args)

        self.assertEqual(result["types"], ["01GTKT", "01/MTT"])

    def test_main_routes_export_subcommand_to_run_export(self):
        argv = [
            "fpt-einvoice-exporter",
            "export",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        ]
        stdout = io.StringIO()

        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("sys.stdout", stdout),
            mock.patch("fpt_einvoice.cli.run_export", return_value={"ok": True}) as run_export,
        ):
            exit_code = cli.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_export.call_args.args[0].command, "export")
        self.assertIn('"ok": true', stdout.getvalue())

    def test_main_keeps_legacy_export_args_working(self):
        argv = [
            "fpt-einvoice-exporter",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        ]
        stdout = io.StringIO()

        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("sys.stdout", stdout),
            mock.patch("fpt_einvoice.cli.run_export", return_value={"ok": True}) as run_export,
        ):
            exit_code = cli.main()

        self.assertEqual(exit_code, 0)
        self.assertIsNone(run_export.call_args.args[0].command)


if __name__ == "__main__":
    unittest.main()
