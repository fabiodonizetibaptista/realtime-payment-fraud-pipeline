"""Valida os artefatos locais da Etapa 11.

Estes testes nao executam SQL nem acessam a Confluent.
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL10 = ROOT / "sql/fraud_detection/pattern/01_match_recognize.sql"
SQL11 = ROOT / "sql/fraud_detection/continuous"


def read(name):
    return (SQL11 / name).read_text(encoding="utf-8")


class TestContinuousProcessing(unittest.TestCase):

    def test_continuous_statement_creates_destination(self):
        sql = read("01_continuous_matches.sql")

        self.assertIn(
            "CREATE TABLE `desafio-final`.`desafio-basic`."
            "`fraud.pattern_matches`",
            sql,
        )
        self.assertIn("'changelog.mode' = 'append'", sql)
        self.assertIn("MATCH_RECOGNIZE", sql)

    def test_reuses_stage10_rule_without_divergence(self):
        # Compara a consulta efetiva, ignorando apenas os
        # comentarios iniciais do arquivo original.
        lines = SQL10.read_text(encoding="utf-8").splitlines()
        while lines and (
            not lines[0].strip()
            or lines[0].lstrip().startswith("--")
        ):
            lines.pop(0)

        original_query = "\n".join(lines).strip().removesuffix(";")
        continuous = read("01_continuous_matches.sql")

        self.assertIn(original_query, continuous)

    def test_inspection_reads_persisted_results(self):
        sql = read("02_inspect_matches.sql")

        self.assertIn(
            "FROM `desafio-final`.`desafio-basic`."
            "`fraud.pattern_matches`",
            sql,
        )
        for column in (
            "card_id",
            "first_rowtime",
            "last_rowtime",
            "transaction_count",
        ):
            self.assertIn(column, sql)

        self.assertIn("LIMIT 50", sql)

    def test_null_cards_are_checked_at_source(self):
        sql = read("03_inspect_null_cards.sql")

        self.assertIn(
            "`payments.public.transactions`",
            sql,
        )
        self.assertIn("WHERE card_id IS NULL", sql)

    def test_inspection_is_read_only(self):
        for filename in (
            "02_inspect_matches.sql",
            "03_inspect_null_cards.sql",
        ):
            with self.subTest(filename=filename):
                statements = [
                    line.strip()
                    for line in read(filename).splitlines()
                    if line.strip()
                    and not line.lstrip().startswith("--")
                ]
                self.assertTrue(statements)
                self.assertTrue(statements[0].startswith("SELECT"))
                self.assertTrue(statements[-1].endswith(";"))


if __name__ == "__main__":
    unittest.main()
