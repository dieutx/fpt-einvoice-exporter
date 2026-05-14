import unittest

import httpx

from fpt_einvoice.api import fetch_invoices


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params):
        self.calls.append((path, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def json_response(status_code, payload):
    return httpx.Response(
        status_code,
        json=payload,
        request=httpx.Request("GET", "https://portal.einvoice.fpt.com.vn/api/sea"),
    )


class ApiFetchTests(unittest.TestCase):
    def test_fetch_invoices_retries_transient_http_errors(self):
        client = FakeClient(
            [
                json_response(502, {"error": "bad gateway"}),
                json_response(200, {"data": [{"inc": 1}]}),
                json_response(200, {"data": []}),
            ]
        )
        sleeps = []

        rows = fetch_invoices(
            client,
            "01/MTT",
            "2025-01-01 00:00:00",
            "2025-01-31 23:59:59",
            2,
            1,
            max_retries=2,
            retry_delay=0.25,
            sleep_func=sleeps.append,
        )

        self.assertEqual(rows, [{"inc": 1}])
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(sleeps, [0.25])

    def test_fetch_invoices_does_not_retry_client_errors(self):
        client = FakeClient([json_response(401, {"error": "unauthorized"})])

        with self.assertRaises(httpx.HTTPStatusError):
            fetch_invoices(
                client,
                "01GTKT",
                "2025-01-01 00:00:00",
                "2025-01-31 23:59:59",
                2,
                100,
                max_retries=2,
                retry_delay=0,
            )

        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
