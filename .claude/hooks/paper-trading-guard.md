---
trigger: pre_tool_use
tool: Bash
match: "(alpaca|trade|order|buy|sell|submit_order|place_order)"
action: warn
---

PAPER TRADING GUARD: This command appears to involve trading operations.

VERIFY before proceeding:
1. Is the Alpaca API key a PAPER TRADING key (not live)?
2. Has this trade been logged to the Decision Registry?
3. Does this comply with the 48-hour minimum hold rule?

If using real money: STOP and get explicit human approval first.
