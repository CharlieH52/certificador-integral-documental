"""Pruebas de las reglas puras de normalización de nombres."""

import unittest

from service.name_normalizer import (
    NormalizationRules,
    append_collision_suffix,
    is_reserved_name,
    max_name_length,
    normalize_name,
    split_extension,
    validate_candidate,
)


class NormalizeNameTests(unittest.TestCase):
    def test_tabla_de_casos(self):
        casos = {
            "Informe, final..pdf": "Informe final.pdf",
            "canción de cuna.mp3": "cancion de cuna.mp3",
            "O'Brien (copia).docx": "OBrien (copia).docx",
            "TAREA 1/2.TXT": "TAREA 12.TXT",
            "Müller_übersicht.tar.gz": "Muller_ubersicht.tar.gz",
            "100% & más!.xlsx": "100 mas.xlsx",
            "  espacios   repetidos  ": "espacios repetidos",
            "archivo---.txt": "archivo.txt",
            "¿Qué?.pdf": "Que.pdf",
            "«Comillas» y “más”.txt": "Comillas y mas.txt",
            "a#b@c$d%e.txt": "abcde.txt",
            "guion-bajo_y guion.txt": "guion-bajo_y guion.txt",
            "paréntesis (1).txt": "parentesis (1).txt",
        }

        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(normalize_name(entrada), esperado)

    def test_conserva_la_ene_y_elimina_la_dieresis(self):
        self.assertEqual(normalize_name("niño.JPG"), "niño.JPG")
        self.assertEqual(normalize_name("NIÑO.JPG"), "NIÑO.JPG")
        self.assertEqual(normalize_name("pingüino.txt"), "pinguino.txt")

    def test_extensiones_compuestas(self):
        self.assertEqual(split_extension("respaldo.tar.gz"), ("respaldo", ".tar.gz"))
        self.assertEqual(split_extension("respaldo.TAR.GZ"), ("respaldo", ".TAR.GZ"))
        self.assertEqual(split_extension("app.min.js"), ("app", ".min.js"))
        self.assertEqual(normalize_name("respaldo final.tar.gz"), "respaldo final.tar.gz")

    def test_los_puntos_del_nombre_se_eliminan(self):
        self.assertEqual(normalize_name("version.1.2.final.pdf"), "version12final.pdf")

    def test_sin_extension_habilitada(self):
        reglas = NormalizationRules(preserve_extensions=False)
        self.assertEqual(normalize_name("informe.final.pdf", rules=reglas), "informefinalpdf")

    def test_nombres_reservados(self):
        self.assertEqual(normalize_name("CON.txt"), "_CON.txt")
        self.assertEqual(normalize_name("lpt9"), "_lpt9")
        self.assertTrue(is_reserved_name("COM1.log"))
        self.assertFalse(is_reserved_name("COM10.log"))

    def test_nombre_vacio_usa_reserva(self):
        self.assertEqual(normalize_name("..."), "SIN_NOMBRE")
        self.assertEqual(normalize_name("///"), "SIN_NOMBRE")
        self.assertEqual(normalize_name(""), "SIN_NOMBRE")

    def test_idempotencia(self):
        muestras = [
            "Informe, final..pdf",
            "niño (2).JPG",
            "O'Brien y Cía.tar.gz",
            "CON.txt",
            "...",
            "100% & más!.xlsx",
            "carpeta / con \\ barras",
        ]
        for muestra in muestras:
            with self.subTest(muestra=muestra):
                primera = normalize_name(muestra)
                self.assertEqual(normalize_name(primera), primera)

    def test_carpetas_no_conservan_extension(self):
        self.assertEqual(normalize_name("carpeta.vieja", is_directory=True), "carpetavieja")


class CollisionSuffixTests(unittest.TestCase):
    def test_sufijo_antes_de_la_extension(self):
        self.assertEqual(append_collision_suffix("informe.pdf", 1), "informe (1).pdf")
        self.assertEqual(
            append_collision_suffix("respaldo.tar.gz", 2), "respaldo (2).tar.gz"
        )
        self.assertEqual(
            append_collision_suffix("carpeta", 3, is_directory=True), "carpeta (3)"
        )


class LengthTests(unittest.TestCase):
    def test_presupuesto_por_ruta(self):
        self.assertEqual(max_name_length(r"C:\x"), 254)
        self.assertEqual(max_name_length("C:\\" + "a" * 250), 5)

    def test_limite_de_componente(self):
        self.assertEqual(max_name_length(r"C:\x", NormalizationRules(max_path_length=999)), 255)

    def test_validacion_de_longitud(self):
        resultado = validate_candidate("x" * 300, r"C:\x")
        self.assertFalse(resultado.is_valid)
        self.assertEqual(resultado.length, 300)


class ValidateCandidateTests(unittest.TestCase):
    def test_nombre_valido(self):
        resultado = validate_candidate("informe final.pdf", r"C:\datos")
        self.assertTrue(resultado.is_valid)
        self.assertEqual(resultado.message, "El nombre es válido.")

    def test_caracteres_invalidos(self):
        for nombre in ["a/b.txt", "a\\b.txt", "a:b.txt", "a?b.txt", "a*b.txt"]:
            with self.subTest(nombre=nombre):
                self.assertFalse(validate_candidate(nombre, r"C:\datos").is_valid)

    def test_espacio_o_punto_final(self):
        self.assertFalse(validate_candidate("informe.txt ", r"C:\datos").is_valid)
        self.assertFalse(validate_candidate("informe.", r"C:\datos").is_valid)

    def test_nombre_reservado(self):
        self.assertFalse(validate_candidate("CON.txt", r"C:\datos").is_valid)

    def test_colision_con_hermano(self):
        resultado = validate_candidate(
            "informe.pdf", r"C:\datos", siblings=["Informe.PDF"]
        )
        self.assertFalse(resultado.is_valid)

    def test_el_propio_nombre_no_es_colision(self):
        resultado = validate_candidate(
            "informe.pdf",
            r"C:\datos",
            siblings=["informe.pdf", "otro.pdf"],
            own_name="informe.pdf",
        )
        self.assertTrue(resultado.is_valid)

    def test_nombre_vacio_o_sin_alfanumericos(self):
        self.assertFalse(validate_candidate("", r"C:\datos").is_valid)
        self.assertFalse(validate_candidate("()", r"C:\datos").is_valid)


if __name__ == "__main__":
    unittest.main()
