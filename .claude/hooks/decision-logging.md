---
trigger: post_tool_use
tool: Bash
match: "(yfinance|get_ticker|stock_info|fundamentals)"
action: remind
---

DECISION REGISTRY REMINDER: You just pulled market data or ran an analysis.

Before moving on, ensure you:
1. Log this analysis to the Decision Registry
2. Include a confidence score (0.0-1.0)
3. State a falsifiable prediction with settlement date
4. Cite the data source and timestamp
