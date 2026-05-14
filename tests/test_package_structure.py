import unittest


class PackageStructureTests(unittest.TestCase):
    def test_package_modules_expose_current_public_functions(self):
        import fpt_einvoice_exporter as legacy

        from fpt_einvoice.config import parse_env_file, resolve_login_inputs
        from fpt_einvoice.export import export_workbook

        self.assertIs(parse_env_file, legacy.parse_env_file)
        self.assertIs(resolve_login_inputs, legacy.resolve_login_inputs)
        self.assertIs(export_workbook, legacy.export_workbook)

    def test_legacy_script_exports_cli_main(self):
        import fpt_einvoice_exporter as legacy

        from fpt_einvoice.cli import main

        self.assertIs(legacy.main, main)


if __name__ == "__main__":
    unittest.main()
