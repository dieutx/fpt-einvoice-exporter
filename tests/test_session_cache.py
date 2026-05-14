import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


if __name__ == "__main__":
    unittest.main()
