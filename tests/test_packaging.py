import sys
import unittest
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = None


class PackagingTests(unittest.TestCase):
    def test_pyproject_defines_console_script(self):
        if tomllib is None:
            self.skipTest("tomllib requires Python 3.11+")

        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))

        self.assertEqual(data["project"]["name"], "fpt-einvoice-exporter")
        self.assertEqual(data["project"]["scripts"]["fpt-einvoice-exporter"], "fpt_einvoice.cli:main")
        self.assertIn("httpx>=0.28.0", data["project"]["dependencies"])


if __name__ == "__main__":
    unittest.main()
