from __future__ import annotations

from unittest.mock import patch

import pytest

from investmentology.cli import main


class TestCLIParsing:
    def test_no_command_fails(self) -> None:
        with pytest.raises(SystemExit):
            main([])

    def test_help_flag(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_screen_command_parses(self) -> None:
        with patch("investmentology.cli.cmd_screen") as mock_cmd:
            main(["screen"])
            mock_cmd.assert_called_once()

    def test_analyze_command_with_tickers(self) -> None:
        with patch("investmentology.cli.cmd_analyze") as mock_cmd:
            main(["analyze", "AAPL", "MSFT"])
            mock_cmd.assert_called_once()
            args = mock_cmd.call_args[0][0]
            assert args.tickers == ["AAPL", "MSFT"]

    def test_analyze_command_with_limit(self) -> None:
        with patch("investmentology.cli.cmd_analyze") as mock_cmd:
            main(["analyze", "--limit", "5"])
            args = mock_cmd.call_args[0][0]
            assert args.limit == 5

    def test_monitor_command(self) -> None:
        with patch("investmentology.cli.cmd_monitor") as mock_cmd:
            main(["monitor"])
            mock_cmd.assert_called_once()

    def test_monitor_premarket(self) -> None:
        with patch("investmentology.cli.cmd_monitor") as mock_cmd:
            main(["monitor", "--premarket"])
            args = mock_cmd.call_args[0][0]
            assert args.premarket is True

    def test_status_command(self) -> None:
        with patch("investmentology.cli.cmd_status") as mock_cmd:
            main(["status"])
            mock_cmd.assert_called_once()

    def test_migrate_command(self) -> None:
        with patch("investmentology.cli.cmd_migrate") as mock_cmd:
            main(["migrate"])
            mock_cmd.assert_called_once()

    def test_verbose_flag(self) -> None:
        with patch("investmentology.cli.cmd_status") as mock_cmd:
            main(["-v", "status"])
            args = mock_cmd.call_args[0][0]
            assert args.verbose is True

    def test_screen_delta(self) -> None:
        with patch("investmentology.cli.cmd_screen") as mock_cmd:
            main(["screen", "--delta", "--previous-run", "42"])
            args = mock_cmd.call_args[0][0]
            assert args.delta is True
            assert args.previous_run == 42
