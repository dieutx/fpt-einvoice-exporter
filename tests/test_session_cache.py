import argparse
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

import fpt_einvoice.auth as auth
import fpt_einvoice.cli as cli


class SessionCacheTests(unittest.TestCase):
    def test_session_cache_round_trips_valid_session(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "bearer-token",
            "fn": "30SHINE Hà Nội",
            "ou": 1,
            "itype": "01GTKT,01/MTT",
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "session.json"

            auth.write_session_cache(cache_path, session)
            cached = auth.read_session_cache(cache_path, "0123456789", "demo_user")

        self.assertEqual(cached, session)

    def test_session_cache_rejects_wrong_account(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "bearer-token",
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "session.json"
            cache_path.write_text(json.dumps({"session": session}), encoding="utf-8")

            cached = auth.read_session_cache(cache_path, "0123456789", "other_user")

        self.assertIsNone(cached)

    def test_run_export_uses_cached_token_without_browser_login(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "cached-token",
            "itype": "01GTKT",
        }

        class FakeClient:
            def close(self):
                pass

        args = argparse.Namespace(
            mst="0123456789",
            username="demo_user",
            password="demo-pass",
            env_file=None,
            from_date="2025-01-01",
            to_date="2025-01-31",
            types="session",
            unl=2,
            page_size=100,
            profile_dir="profile",
            output_dir="output",
            output_name=None,
            headed=False,
            login_wait_seconds=35,
            reuse_token=True,
            session_file=None,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args.profile_dir = str(tmp_path / "profile")
            args.output_dir = str(tmp_path / "output")
            auth.write_session_cache(tmp_path / "profile" / "fpt_session.json", session)

            with (
                mock.patch("fpt_einvoice.cli.portal_login") as portal_login,
                mock.patch("fpt_einvoice.cli.build_client", return_value=FakeClient()) as build_client,
                mock.patch("fpt_einvoice.cli.fetch_invoices", return_value=[]) as fetch_invoices,
            ):
                result = cli.run_export(args)

        portal_login.assert_not_called()
        build_client.assert_called_once_with("cached-token")
        fetch_invoices.assert_called_once()
        self.assertTrue(result["ok"])

    def test_run_export_passes_login_wait_when_cache_misses(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "fresh-token",
            "itype": "01GTKT",
        }

        class FakeContext:
            def close(self):
                pass

        class FakeClient:
            def close(self):
                pass

        args = argparse.Namespace(
            mst="0123456789",
            username="demo_user",
            password="demo-pass",
            env_file=None,
            from_date="2025-01-01",
            to_date="2025-01-31",
            types="session",
            unl=2,
            page_size=100,
            profile_dir="profile",
            output_dir="output",
            output_name=None,
            headed=True,
            login_wait_seconds=300,
            reuse_token=True,
            session_file=None,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args.profile_dir = str(tmp_path / "profile")
            args.output_dir = str(tmp_path / "output")

            with (
                mock.patch(
                    "fpt_einvoice.cli.portal_login",
                    return_value={
                        "context": FakeContext(),
                        "page": object(),
                        "session": session,
                        "token": "fresh-token",
                    },
                ) as portal_login,
                mock.patch("fpt_einvoice.cli.build_client", return_value=FakeClient()),
                mock.patch("fpt_einvoice.cli.fetch_invoices", return_value=[]),
            ):
                cli.run_export(args)

        self.assertEqual(portal_login.call_args.kwargs["login_wait_seconds"], 300)

    def test_run_export_invalidates_cached_token_on_unauthorized_api_response(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "expired-token",
            "itype": "01GTKT",
        }

        class FakeClient:
            def close(self):
                pass

        args = argparse.Namespace(
            mst="0123456789",
            username="demo_user",
            password="demo-pass",
            env_file=None,
            from_date="2025-01-01",
            to_date="2025-01-31",
            types="session",
            unl=2,
            page_size=100,
            profile_dir="profile",
            output_dir="output",
            output_name=None,
            headed=False,
            login_wait_seconds=35,
            reuse_token=True,
            session_file=None,
            max_retries=0,
            retry_delay=0,
            resume=False,
            continue_on_error=False,
        )
        response = httpx.Response(
            401,
            json={"error": "unauthorized"},
            request=httpx.Request("GET", "https://portal.einvoice.fpt.com.vn/api/sea"),
        )
        unauthorized = httpx.HTTPStatusError("unauthorized", request=response.request, response=response)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args.profile_dir = str(tmp_path / "profile")
            args.output_dir = str(tmp_path / "output")
            cache_path = tmp_path / "profile" / "fpt_session.json"
            auth.write_session_cache(cache_path, session)

            with (
                mock.patch("fpt_einvoice.cli.portal_login") as portal_login,
                mock.patch("fpt_einvoice.cli.build_client", return_value=FakeClient()),
                mock.patch("fpt_einvoice.cli.fetch_invoices", side_effect=unauthorized),
                self.assertRaisesRegex(RuntimeError, "Token cache hết hạn"),
            ):
                cli.run_export(args)

            self.assertFalse(cache_path.exists())

        portal_login.assert_not_called()

    def test_run_export_continue_on_error_writes_successful_types_and_metadata_errors(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "cached-token",
            "itype": "ERR,OK",
        }

        class FakeClient:
            def close(self):
                pass

        args = argparse.Namespace(
            mst="0123456789",
            username="demo_user",
            password="demo-pass",
            env_file=None,
            from_date="2025-01-01",
            to_date="2025-01-31",
            types="session",
            unl=2,
            page_size=100,
            profile_dir="profile",
            output_dir="output",
            output_name=None,
            headed=False,
            login_wait_seconds=35,
            reuse_token=True,
            session_file=None,
            max_retries=0,
            retry_delay=0,
            resume=False,
            continue_on_error=True,
        )
        response = httpx.Response(
            500,
            json={"error": "server"},
            request=httpx.Request("GET", "https://portal.einvoice.fpt.com.vn/api/sea"),
        )
        server_error = httpx.HTTPStatusError("server error", request=response.request, response=response)

        def fetch_side_effect(client, type_code, *args, **kwargs):
            if type_code == "ERR":
                raise server_error
            return [{"inc": 10, "idt": "2025-01-02T00:00:00"}]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args.profile_dir = str(tmp_path / "profile")
            args.output_dir = str(tmp_path / "output")
            auth.write_session_cache(tmp_path / "profile" / "fpt_session.json", session)

            with (
                mock.patch("fpt_einvoice.cli.build_client", return_value=FakeClient()),
                mock.patch("fpt_einvoice.cli.fetch_invoices", side_effect=fetch_side_effect),
            ):
                result = cli.run_export(args)

            metadata = json.loads((tmp_path / "output" / "metadata.json").read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertEqual(result["counts"], {"OK": 1})
        self.assertIn("ERR", result["errors"])
        self.assertEqual(metadata["counts"], {"OK": 1})
        self.assertIn("ERR", metadata["errors"])

    def test_run_export_partial_result_includes_resume_warning(self):
        session = {
            "uid": "0123456789.demo_user",
            "token": "cached-token",
            "itype": "ERR,OK",
        }

        class FakeClient:
            def close(self):
                pass

        args = argparse.Namespace(
            mst="0123456789",
            username="demo_user",
            password="demo-pass",
            env_file=None,
            from_date="2025-01-01",
            to_date="2025-01-31",
            types="session",
            unl=2,
            page_size=100,
            min_page_size=10,
            adaptive_page_size=True,
            profile_dir="profile",
            output_dir="output",
            output_name=None,
            headed=False,
            login_wait_seconds=35,
            reuse_token=True,
            session_file=None,
            max_retries=0,
            retry_delay=0,
            resume=False,
            continue_on_error=True,
        )
        response = httpx.Response(
            502,
            json={"error": "bad gateway"},
            request=httpx.Request("GET", "https://portal.einvoice.fpt.com.vn/api/sea"),
        )
        gateway_error = httpx.HTTPStatusError("bad gateway", request=response.request, response=response)

        def fetch_side_effect(client, type_code, *args, **kwargs):
            if type_code == "ERR":
                raise gateway_error
            return [{"inc": 10, "idt": "2025-01-02T00:00:00"}]

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            args.profile_dir = str(tmp_path / "profile")
            args.output_dir = str(tmp_path / "output")
            auth.write_session_cache(tmp_path / "profile" / "fpt_session.json", session)

            with (
                mock.patch("fpt_einvoice.cli.build_client", return_value=FakeClient()),
                mock.patch("fpt_einvoice.cli.fetch_invoices", side_effect=fetch_side_effect),
            ):
                result = cli.run_export(args)

            metadata = json.loads((tmp_path / "output" / "metadata.json").read_text(encoding="utf-8"))

        self.assertFalse(result["ok"])
        self.assertIn("warnings", result)
        self.assertTrue(any("--resume" in warning for warning in result["warnings"]))
        self.assertEqual(metadata["warnings"], result["warnings"])

    def test_main_prints_runtime_errors_without_traceback(self):
        argv = [
            "fpt-einvoice-exporter",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        ]
        stderr = io.StringIO()

        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("sys.stderr", stderr),
            mock.patch("fpt_einvoice.cli.run_export", side_effect=RuntimeError("Token cache hết hạn")),
            self.assertRaises(SystemExit) as cm,
        ):
            cli.main()

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("Token cache hết hạn", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_main_prints_keyboard_interrupt_without_traceback(self):
        argv = [
            "fpt-einvoice-exporter",
            "--from-date",
            "2025-01-01",
            "--to-date",
            "2025-01-31",
        ]
        stderr = io.StringIO()

        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("sys.stderr", stderr),
            mock.patch("fpt_einvoice.cli.run_export", side_effect=KeyboardInterrupt()),
        ):
            exit_code = cli.main()

        self.assertEqual(exit_code, 130)
        self.assertIn("--resume", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
