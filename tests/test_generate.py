"""Pruebas del cálculo de huellas hash con el algoritmo configurado."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from service.generate import CertifyMaker, calculate_file_hash, resolve_hash_algorithm


class HashAlgorithmTests(unittest.TestCase):
    """Verifica la resolución de algoritmos y el cálculo por bloques."""

    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_directory.name) / "muestra.txt"
        self.file_path.write_text("abc", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_sha256_is_the_default_algorithm(self) -> None:
        expected = (
            "BA7816BF8F01CFEA414140DE5DAE2223"
            "B00361A396177A9CB410FF61F20015AD"
        )
        self.assertEqual(calculate_file_hash(str(self.file_path)), expected)

    def test_configured_algorithm_is_used(self) -> None:
        expected = "900150983CD24FB0D6963F7D28E17F72"
        self.assertEqual(
            calculate_file_hash(str(self.file_path), "MD5"),
            expected,
        )

    def test_common_algorithm_aliases_are_resolved(self) -> None:
        self.assertEqual(resolve_hash_algorithm("SHA-256"), "sha256")
        self.assertEqual(resolve_hash_algorithm("sha3-256"), "sha3_256")
        self.assertEqual(resolve_hash_algorithm("SHA512"), "sha512")

    def test_unsupported_algorithm_raises_a_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "no soportado"):
            resolve_hash_algorithm("NO-EXISTE")

    def test_certification_uses_the_configured_algorithm(self) -> None:
        with tempfile.TemporaryDirectory() as output_directory:
            with patch("config.DEFAULT_HASH_ALGORITHM", "MD5"), patch(
                "config.OUTPUT_DIRECTORY", output_directory
            ):
                maker = CertifyMaker(
                    self.temp_directory.name,
                    "prueba",
                    save_json=True,
                    save_sqlite=False,
                )

            report_path = Path(output_directory) / "prueba.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertEqual(maker.hash_algorithm, "MD5")
            self.assertEqual(report[0]["Algorithm"], "MD5")
            self.assertEqual(report[0]["Hash"], "900150983CD24FB0D6963F7D28E17F72")


if __name__ == "__main__":
    unittest.main()
