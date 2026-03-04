from __future__ import annotations

import json

from investmentology.registry.db import Database


class QuantGateRepo:
    def __init__(self, db: Database) -> None:
        self._db = db

    def create_quant_gate_run(
        self, universe_size: int, passed_count: int,
        config: dict, data_quality: dict | None = None,
    ) -> int:
        rows = self._db.execute(
            "INSERT INTO invest.quant_gate_runs (run_date, universe_size, passed_count, config, data_quality) "
            "VALUES (CURRENT_DATE, %s, %s, %s, %s) RETURNING id",
            (universe_size, passed_count, json.dumps(config), json.dumps(data_quality or {})),
        )
        return rows[0]["id"]

    def insert_quant_gate_results(self, run_id: int, results: list[dict]) -> int:
        query = """
            INSERT INTO invest.quant_gate_results (
                run_id, ticker, earnings_yield, roic, ey_rank, roic_rank,
                combined_rank, piotroski_score, altman_z_score,
                composite_score, altman_zone
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                run_id, r["ticker"], r.get("earnings_yield"), r.get("roic"),
                r.get("ey_rank"), r.get("roic_rank"), r.get("combined_rank"),
                r.get("piotroski_score"), r.get("altman_z_score"),
                r.get("composite_score"), r.get("altman_zone"),
            )
            for r in results
        ]
        return self._db.execute_many(query, params)
