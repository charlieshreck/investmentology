from __future__ import annotations

from enum import StrEnum


class WatchlistState(StrEnum):
    UNIVERSE = "UNIVERSE"
    CANDIDATE = "CANDIDATE"
    ASSESSED = "ASSESSED"
    CONVICTION_BUY = "CONVICTION_BUY"
    WATCHLIST_EARLY = "WATCHLIST_EARLY"
    WATCHLIST_CATALYST = "WATCHLIST_CATALYST"
    REJECTED = "REJECTED"
    CONFLICT_REVIEW = "CONFLICT_REVIEW"
    POSITION_HOLD = "POSITION_HOLD"
    POSITION_TRIM = "POSITION_TRIM"
    POSITION_SELL = "POSITION_SELL"


VALID_TRANSITIONS: dict[WatchlistState, set[WatchlistState]] = {
    WatchlistState.UNIVERSE: {WatchlistState.CANDIDATE},
    WatchlistState.CANDIDATE: {WatchlistState.ASSESSED, WatchlistState.REJECTED},
    WatchlistState.ASSESSED: {
        WatchlistState.CONVICTION_BUY,
        WatchlistState.WATCHLIST_EARLY,
        WatchlistState.WATCHLIST_CATALYST,
        WatchlistState.REJECTED,
        WatchlistState.CONFLICT_REVIEW,
    },
    WatchlistState.CONVICTION_BUY: {WatchlistState.POSITION_HOLD, WatchlistState.REJECTED},
    WatchlistState.WATCHLIST_EARLY: {
        WatchlistState.ASSESSED,
        WatchlistState.REJECTED,
        WatchlistState.CONVICTION_BUY,
    },
    WatchlistState.WATCHLIST_CATALYST: {
        WatchlistState.ASSESSED,
        WatchlistState.REJECTED,
        WatchlistState.CONVICTION_BUY,
    },
    WatchlistState.CONFLICT_REVIEW: {
        WatchlistState.ASSESSED,
        WatchlistState.REJECTED,
        WatchlistState.CONVICTION_BUY,
    },
    WatchlistState.POSITION_HOLD: {WatchlistState.POSITION_TRIM, WatchlistState.POSITION_SELL},
    WatchlistState.POSITION_TRIM: {WatchlistState.POSITION_HOLD, WatchlistState.POSITION_SELL},
    WatchlistState.POSITION_SELL: set(),
    WatchlistState.REJECTED: set(),
}


def validate_transition(current: WatchlistState, target: WatchlistState) -> bool:
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed
