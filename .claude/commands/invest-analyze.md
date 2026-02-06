Analyze a single stock through available pipeline layers.

Given a ticker symbol (passed as $ARGUMENTS or ask for it), run the stock through each implemented layer:

1. **Quant Gate**: Pull fundamentals via yfinance. Calculate ROIC and Earnings Yield. Does it pass the quantitative threshold?
2. **Competence Filter** (if implemented): Is the business understandable? What is its moat?
3. **Multi-Agent Analysis** (if implemented): Run through Warren/Soros/Simons/Auditor agents
4. **Adversarial Check** (if implemented): Apply Munger bias checklist and inversion

For each layer, output:
- Score (1-10)
- Key findings
- Red flags
- Confidence level

End with a structured summary:
```
Ticker: AAPL
Overall Score: 7.5/10
Recommendation: WATCHLIST | BUY | PASS
Confidence: 0.75
Key Thesis: [one sentence]
Primary Risk: [one sentence]
```

ALWAYS log the analysis to the Decision Registry with a falsifiable prediction and settlement date.
