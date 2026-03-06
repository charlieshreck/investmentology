"""Tests for pipeline state operations.

Uses mock DB to test state management logic without database dependency.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from investmentology.pipeline.state import (
    STALENESS_HOURS,
    STEP_AGENT_PREFIX,
    STEP_DATA_FETCH,
    STEP_DATA_VALIDATE,
    STEP_DEBATE,
    STEP_SYNTHESIS,
)


class TestConstants:
    def test_staleness_window(self):
        assert STALENESS_HOURS == 24

    def test_step_names(self):
        assert STEP_DATA_FETCH == "data_fetch"
        assert STEP_DATA_VALIDATE == "data_validate"
        assert STEP_AGENT_PREFIX == "agent:"
        assert STEP_DEBATE == "debate"
        assert STEP_SYNTHESIS == "synthesis"

    def test_step_dependency_order(self):
        from investmentology.pipeline.state import (
            STEP_ADVERSARIAL,
            STEP_GATE_DECISION,
            STEP_PRE_FILTER,
            STEP_RESEARCH,
            STEP_SCREENER_PREFIX,
        )
        # Verify all steps exist (regression guard)
        steps = [
            STEP_DATA_FETCH, STEP_DATA_VALIDATE, STEP_PRE_FILTER,
            STEP_SCREENER_PREFIX, STEP_GATE_DECISION, STEP_RESEARCH,
            STEP_AGENT_PREFIX, STEP_DEBATE, STEP_ADVERSARIAL, STEP_SYNTHESIS,
        ]
        assert len(steps) == 10
        assert all(isinstance(s, str) for s in steps)


class TestCreateCycle:
    def test_creates_cycle(self):
        from investmentology.pipeline.state import create_cycle

        mock_db = MagicMock()
        cycle_id = uuid4()
        mock_db.execute.return_value = [{"id": cycle_id}]

        result = create_cycle(mock_db, ticker_count=5)
        assert result == cycle_id
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "INSERT INTO invest.pipeline_cycles" in call_args[0][0]
        assert call_args[0][1] == (5,)


class TestCompleteCycle:
    def test_marks_completed(self):
        from investmentology.pipeline.state import complete_cycle

        mock_db = MagicMock()
        mock_db.execute.return_value = []
        cycle_id = uuid4()

        complete_cycle(mock_db, cycle_id)
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        assert "status = 'completed'" in call_args[0][0]
        assert call_args[0][1] == (cycle_id,)


class TestExpireOldCycles:
    def test_expires_stale_cycles(self):
        from investmentology.pipeline.state import expire_old_cycles

        mock_db = MagicMock()
        mock_db.execute.return_value = [{"id": uuid4()}, {"id": uuid4()}]

        count = expire_old_cycles(mock_db)
        assert count == 2
        call_args = mock_db.execute.call_args
        assert "status = 'expired'" in call_args[0][0]
        assert "status = 'active'" in call_args[0][0]

    def test_no_stale_cycles(self):
        from investmentology.pipeline.state import expire_old_cycles

        mock_db = MagicMock()
        mock_db.execute.return_value = []

        count = expire_old_cycles(mock_db)
        assert count == 0


class TestCreateStep:
    def test_creates_step(self):
        from investmentology.pipeline.state import create_step

        mock_db = MagicMock()
        cycle_id = uuid4()
        mock_db.execute.return_value = [{"id": 42}]

        result = create_step(mock_db, cycle_id=cycle_id, ticker="AAPL", step=STEP_DATA_FETCH)
        assert result == 42
        call_args = mock_db.execute.call_args
        assert "INSERT INTO invest.pipeline_state" in call_args[0][0]
