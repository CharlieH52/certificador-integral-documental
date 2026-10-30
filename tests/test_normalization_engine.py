"""Pruebas del planificador, la aplicación y la reversión."""

import json
import os
import tempfile
import unittest
from unittest import mock

import config
from service.name_normalizer import NormalizationRules
from service.normalization_engine import (
    NormalizationApplier,
    NormalizationCancelled,
    NormalizationError,
    NormalizationPlan,
    NormalizationPlanner,
    NormalizationUndo,
    PlanEntry,
    ReviewDecision,
)


def write_file(path: str, content: str = "contenido") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


class EngineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)

        self.root = os.path.join(self.temporary.name, "origen")
        os.makedirs(self.root)

        self.output_patch = mock.patch.object(
            config, "OUTPUT_DIRECTORY", os.path.join(self.temporary.name, "salida")
        )
        self.output_patch.start()
        self.addCleanup(self.output_patch.stop)

    def names_in(self, directory: str) -> set[str]:
        return set(os.listdir(directory))


class RenamePlanTests(EngineTestCase):
    def test_renombra_archivos_y_carpetas_con_reversion(self):
        write_file(os.path.join(self.root, "Informe, final..pdf"))
        write_file(os.path.join(self.root, "carpeta, vieja", "nota, final.txt"))

        plan = NormalizationPlanner(self.root).build()

        # La planificación no modifica el disco.
        self.assertIn("Informe, final..pdf", self.names_in(self.root))
        self.assertEqual(len(plan.changes), 3)

        result = NormalizationApplier(plan).apply()

        self.assertEqual(result.renamed, 3)
        self.assertIsNotNone(result.journal_path)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Informe final.pdf")))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.root, "carpeta vieja", "nota final.txt")
            )
        )

        undo = NormalizationUndo(result.journal_path).undo()

        self.assertEqual(undo.restored, 3)
        self.assertTrue(os.path.isfile(os.path.join(self.root, "Informe, final..pdf")))
        self.assertTrue(
            os.path.isfile(
                os.path.join(self.root, "carpeta, vieja", "nota, final.txt")
            )
        )

    def test_resuelve_colisiones_de_forma_determinista(self):
        write_file(os.path.join(self.root, "informe.pdf"), "original")
        write_file(os.path.join(self.root, "informe, .pdf"), "duplicado")

        plan = NormalizationPlanner(self.root).build()
        NormalizationApplier(plan).apply()

        self.assertTrue(os.path.isfile(os.path.join(self.root, "informe.pdf")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, "informe (1).pdf")))

    def test_no_renombra_el_directorio_raiz(self):
        root = os.path.join(self.temporary.name, "origen, raro")
        os.makedirs(root)
        write_file(os.path.join(root, "nota, uno.txt"))

        plan = NormalizationPlanner(root).build()

        self.assertNotIn(root, {entry.source_path for entry in plan.entries})
        self.assertEqual(os.path.basename(plan.root), "origen, raro")

    def test_omite_directorios_y_archivos_del_sistema(self):
        write_file(os.path.join(self.root, ".git", "config"))
        write_file(os.path.join(self.root, "node_modules", "paquete.js"))
        write_file(os.path.join(self.root, "desktop.ini"))
        write_file(os.path.join(self.root, "nota, uno.txt"))

        plan = NormalizationPlanner(self.root).build()
        sources = {entry.source_path for entry in plan.entries}

        self.assertEqual(len(plan.entries), 1)
        self.assertTrue(any(source.endswith("nota, uno.txt") for source in sources))

    def test_no_colisiona_con_archivo_ignorado(self):
        write_file(os.path.join(self.root, "desktop.ini"), "sistema")
        write_file(os.path.join(self.root, "desktop,.ini"), "usuario")

        plan = NormalizationPlanner(self.root).build()
        NormalizationApplier(plan).apply()

        with open(os.path.join(self.root, "desktop.ini"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "sistema")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "desktop (1).ini")))

    def test_diario_en_carpeta_de_salida(self):
        write_file(os.path.join(self.root, "nota, uno.txt"))
        plan = NormalizationPlanner(self.root).build()
        result = NormalizationApplier(plan).apply()

        self.assertIsNotNone(result.journal_path)
        self.assertTrue(
            os.path.abspath(result.journal_path).startswith(
                os.path.abspath(os.path.join(self.temporary.name, "salida"))
            )
        )
        with open(result.journal_path, "r", encoding="utf-8") as file:
            journal = json.load(file)
        self.assertEqual(journal["mode"], "rename")
        self.assertEqual(journal["renamed"], 1)


class TwoPhaseRenameTests(EngineTestCase):
    def test_intercambio_de_nombres_y_reversion(self):
        write_file(os.path.join(self.root, "a.txt"), "contenido A")
        write_file(os.path.join(self.root, "b.txt"), "contenido B")

        entries = [
            PlanEntry(
                source_path=os.path.join(self.root, "a.txt"),
                original_name="a.txt",
                final_name="b.txt",
                is_directory=False,
                parent_source=self.root,
                parent_target=self.root,
            ),
            PlanEntry(
                source_path=os.path.join(self.root, "b.txt"),
                original_name="b.txt",
                final_name="a.txt",
                is_directory=False,
                parent_source=self.root,
                parent_target=self.root,
            ),
        ]
        plan = NormalizationPlan(root=self.root, mode="rename", entries=entries)

        result = NormalizationApplier(plan).apply()

        self.assertEqual(result.renamed, 2)
        self.assertEqual(result.errors, [])
        with open(os.path.join(self.root, "a.txt"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "contenido B")
        with open(os.path.join(self.root, "b.txt"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "contenido A")

        undo = NormalizationUndo(result.journal_path).undo()

        self.assertEqual(undo.restored, 2)
        self.assertEqual(undo.errors, [])
        with open(os.path.join(self.root, "a.txt"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "contenido A")
        with open(os.path.join(self.root, "b.txt"), encoding="utf-8") as file:
            self.assertEqual(file.read(), "contenido B")


class CopyPlanTests(EngineTestCase):
    def test_copia_normalizada_y_reversion(self):
        write_file(os.path.join(self.root, "nota, final.txt"), "origen")
        write_file(os.path.join(self.root, "sub, carpeta", "dato, uno.txt"), "dato")

        destination = os.path.join(self.temporary.name, "destino")
        os.makedirs(destination)
        write_file(os.path.join(destination, "nota final.txt"), "preexistente")

        plan = NormalizationPlanner(
            self.root, mode="copy", destination_root=destination
        ).build()

        self.assertEqual(len(plan.changes), 3)

        result = NormalizationApplier(plan).apply()

        self.assertEqual(result.copied_files, 2)
        self.assertTrue(os.path.isfile(os.path.join(destination, "nota final.txt")))
        self.assertTrue(
            os.path.isfile(os.path.join(destination, "nota final (1).txt"))
        )
        self.assertTrue(
            os.path.isfile(
                os.path.join(destination, "sub carpeta", "dato uno.txt")
            )
        )
        with open(
            os.path.join(destination, "nota final.txt"), "r", encoding="utf-8"
        ) as file:
            self.assertEqual(file.read(), "preexistente")

        undo = NormalizationUndo(result.journal_path).undo()

        self.assertEqual(undo.removed_files, 2)
        self.assertTrue(os.path.isfile(os.path.join(destination, "nota final.txt")))
        self.assertFalse(os.path.exists(os.path.join(destination, "nota final (1).txt")))
        self.assertFalse(os.path.exists(os.path.join(destination, "sub carpeta")))

    def test_rechaza_destino_dentro_del_origen(self):
        with self.assertRaises(NormalizationError):
            NormalizationPlanner(
                self.root,
                mode="copy",
                destination_root=os.path.join(self.root, "normalizado"),
            ).build()


class ReviewTests(EngineTestCase):
    def build_rules(self) -> NormalizationRules:
        # Presupuesto de 12 caracteres para forzar la revisión manual.
        return NormalizationRules(max_path_length=len(os.path.abspath(self.root)) + 13)

    def test_acepta_nombre_manual(self):
        write_file(os.path.join(self.root, "documento, demasiado largo.txt"))
        decisions = []

        def resolver(entry, reason):
            decisions.append((entry.final_name, reason))
            return ReviewDecision("accept", "corto.txt")

        plan = NormalizationPlanner(
            self.root, resolver=resolver, rules=self.build_rules()
        ).build()

        self.assertEqual(len(decisions), 1)
        self.assertEqual(plan.changes[0].final_name, "corto.txt")

        NormalizationApplier(plan).apply()
        self.assertTrue(os.path.isfile(os.path.join(self.root, "corto.txt")))
        self.assertFalse(
            os.path.exists(os.path.join(self.root, "documento, demasiado largo.txt"))
        )

    def test_omite_el_renombrado(self):
        write_file(os.path.join(self.root, "documento, demasiado largo.txt"))

        plan = NormalizationPlanner(
            self.root,
            resolver=lambda entry, reason: ReviewDecision("skip"),
            rules=self.build_rules(),
        ).build()

        self.assertEqual(len(plan.changes), 0)
        self.assertEqual(len(plan.skipped_entries), 1)

        result = NormalizationApplier(plan).apply()

        self.assertEqual(result.renamed, 0)
        self.assertIsNone(result.journal_path)
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "documento, demasiado largo.txt"))
        )

    def test_cancela_la_planificacion(self):
        write_file(os.path.join(self.root, "documento, demasiado largo.txt"))

        with self.assertRaises(NormalizationCancelled):
            NormalizationPlanner(
                self.root,
                resolver=lambda entry, reason: ReviewDecision("cancel"),
                rules=self.build_rules(),
            ).build()

    def test_nombre_manual_invalido_se_omite(self):
        write_file(os.path.join(self.root, "documento, demasiado largo.txt"))

        plan = NormalizationPlanner(
            self.root,
            resolver=lambda entry, reason: ReviewDecision("accept", "a/b.txt"),
            rules=self.build_rules(),
        ).build()

        self.assertEqual(len(plan.skipped_entries), 1)
        self.assertTrue(plan.errors)


if __name__ == "__main__":
    unittest.main()
