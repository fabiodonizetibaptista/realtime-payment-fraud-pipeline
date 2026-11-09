"""Testes locais do contrato da Etapa 10.

Os cenarios usam um avaliador de referencia em Python.
Eles NAO substituem a execucao real do SQL no Flink.
"""

import re
import unittest
from datetime import datetime, timedelta
from pathlib import Path

SQL_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql/etapa-10/01_match_recognize.sql"
)


def evaluate_reference(events):
    """Simula T{3}, WITHIN 60s e SKIP PAST LAST ROW.

    O avaliador trabalha por cartao, em ordem temporal,
    e nao reutiliza eventos de uma correspondencia concluida.
    """
    matches = []

    for card_id in sorted({event["card_id"] for event in events}):
        partition = sorted(
            (e for e in events if e["card_id"] == card_id),
            key=lambda e: e["rowtime"],
        )

        index = 0
        while index <= len(partition) - 3:
            group = partition[index:index + 3]

            if all(e["amount"] > 0 for e in group) and (
                group[-1]["rowtime"] - group[0]["rowtime"]
            ) <= timedelta(seconds=60):
                matches.append(
                    (card_id, tuple(e["id"] for e in group))
                )
                index += 3
            else:
                index += 1

    return matches


def tx(number, card="CARD-1", seconds=0, amount=10):
    return {
        "id": number,
        "card_id": card,
        "rowtime": datetime(2026, 11, 9) + timedelta(seconds=seconds),
        "amount": amount,
    }


class TestSqlContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(encoding="utf-8")

    def test_temporal_join_preserved(self):
        self.assertIn("FOR SYSTEM_TIME AS OF", self.sql)
        self.assertIn("t.account_id = a.account_id", self.sql)

    def test_match_recognize_structure(self):
        required = [
            "MATCH_RECOGNIZE",
            "PARTITION BY card_id",
            "ORDER BY transaction_rowtime",
            "ONE ROW PER MATCH",
            "AFTER MATCH SKIP PAST LAST ROW",
            "PATTERN (T{3})",
            "WITHIN INTERVAL '60' SECOND",
            "T AS T.amount > 0",
        ]
        for clause in required:
            with self.subTest(clause=clause):
                self.assertIn(clause, self.sql)

    def test_first_and_last_rowtime(self):
        self.assertIn("FIRST(T.transaction_rowtime)", self.sql)
        self.assertIn("LAST(T.transaction_rowtime)", self.sql)

    def test_card_id_non_null_filter(self):
        self.assertIn(
            "WHERE t.card_id IS NOT NULL", self.sql
        )

    def test_read_only_query(self):
        normalized = re.sub(
            r"(?m)^\s*--.*$", "", self.sql
        ).strip().upper()

        self.assertTrue(normalized.startswith("WITH "))
        self.assertNotRegex(
            normalized,
            r"\b(INSERT|CREATE|DROP|DELETE|UPDATE|ALTER)\b",
        )


class TestReferenceBehavior(unittest.TestCase):
    def test_three_transactions_within_60_seconds(self):
        events = [tx(1, seconds=0), tx(2, seconds=18),
                  tx(3, seconds=45)]
        self.assertEqual(
            evaluate_reference(events),
            [("CARD-1", (1, 2, 3))],
        )

    def test_exactly_60_seconds(self):
        events = [tx(1, seconds=0), tx(2, seconds=30),
                  tx(3, seconds=60)]
        self.assertEqual(len(evaluate_reference(events)), 1)

    def test_over_60_seconds(self):
        events = [tx(1, seconds=0), tx(2, seconds=30),
                  tx(3, seconds=61)]
        self.assertEqual(evaluate_reference(events), [])

    def test_different_cards_do_not_mix(self):
        events = [tx(1, "A", 0), tx(2, "B", 10),
                  tx(3, "A", 20)]
        self.assertEqual(evaluate_reference(events), [])

    def test_non_positive_amount_breaks_sequence(self):
        events = [tx(1, seconds=0), tx(2, seconds=10, amount=0),
                  tx(3, seconds=20), tx(4, seconds=30)]
        self.assertEqual(evaluate_reference(events), [])

    def test_negative_amount(self):
        events = [tx(1, seconds=0), tx(2, seconds=10, amount=-5),
                  tx(3, seconds=20)]
        self.assertEqual(evaluate_reference(events), [])

    def test_skip_past_last_row(self):
        events = [tx(i, seconds=i * 5) for i in range(1, 7)]
        self.assertEqual(
            evaluate_reference(events),
            [
                ("CARD-1", (1, 2, 3)),
                ("CARD-1", (4, 5, 6)),
            ],
        )

    def test_four_transactions_generate_one_match(self):
        events = [tx(i, seconds=i * 5) for i in range(1, 5)]
        self.assertEqual(
            evaluate_reference(events),
            [("CARD-1", (1, 2, 3))],
        )

    def test_out_of_order_input(self):
        events = [tx(3, seconds=30), tx(1, seconds=0),
                  tx(2, seconds=15)]
        self.assertEqual(
            evaluate_reference(events),
            [("CARD-1", (1, 2, 3))],
        )


if __name__ == "__main__":
    unittest.main()
