#!/usr/bin/env python3
"""Compatibility wrapper for the FPT eInvoice exporter CLI.

The implementation lives in the `fpt_einvoice` package. This file keeps the
original `python fpt_einvoice_exporter.py ...` command working.
"""

from fpt_einvoice.api import build_client, fetch_invoices, resolve_types
from fpt_einvoice.auth import (
    portal_login,
    read_session_cache,
    session_account_matches,
    wait_for_enabled,
    wait_for_session,
    write_session_cache,
)
from fpt_einvoice.cli import build_parser, main, run_export
from fpt_einvoice.config import load_login_env, parse_env_file, resolve_login_inputs, strip_inline_comment
from fpt_einvoice.constants import (
    BASE_URL,
    CONVERTED_INV_LABELS,
    INVOICE_STATUS_LABELS,
    KNOWN_TYPE_LABELS,
    LOGIN_ENV_MAP,
    MAIL_STATUS_LABELS,
    MINUTES_SIGN_STATUS_LABELS,
    PRIMARY_COLUMNS,
    STATUS_RECEIVED_LABELS,
    UI_EXPORT_COLUMNS,
)
from fpt_einvoice.export import (
    _sort_invoice_rows,
    autosize_columns,
    build_ui_export_row,
    export_workbook,
    flatten_invoice,
    normalize_value,
    resolve_business_class,
    resolve_cancel_date,
    resolve_dtl_invs_status,
    resolve_ou_display,
    sheet_name_for_type,
    write_json,
    write_sheet,
)
from fpt_einvoice.formatting import display_date, display_number, localize_iso, lookup_label, parse_date
from fpt_einvoice.log import eprint

__all__ = [
    "BASE_URL",
    "CONVERTED_INV_LABELS",
    "INVOICE_STATUS_LABELS",
    "KNOWN_TYPE_LABELS",
    "LOGIN_ENV_MAP",
    "MAIL_STATUS_LABELS",
    "MINUTES_SIGN_STATUS_LABELS",
    "PRIMARY_COLUMNS",
    "STATUS_RECEIVED_LABELS",
    "UI_EXPORT_COLUMNS",
    "_sort_invoice_rows",
    "autosize_columns",
    "build_client",
    "build_parser",
    "build_ui_export_row",
    "display_date",
    "display_number",
    "eprint",
    "export_workbook",
    "fetch_invoices",
    "flatten_invoice",
    "load_login_env",
    "localize_iso",
    "lookup_label",
    "main",
    "normalize_value",
    "parse_date",
    "parse_env_file",
    "portal_login",
    "read_session_cache",
    "resolve_business_class",
    "resolve_cancel_date",
    "resolve_dtl_invs_status",
    "resolve_login_inputs",
    "resolve_ou_display",
    "resolve_types",
    "run_export",
    "session_account_matches",
    "sheet_name_for_type",
    "strip_inline_comment",
    "wait_for_enabled",
    "wait_for_session",
    "write_json",
    "write_session_cache",
    "write_sheet",
]


if __name__ == "__main__":
    raise SystemExit(main())
