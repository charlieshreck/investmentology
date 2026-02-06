Run the Greenblatt Magic Formula quantitative screening gate.

Screen the full US equity universe using ROIC (Return on Invested Capital) and Earnings Yield. Steps:

1. Use yfinance to pull fundamental data for S&P 500 + Russell 2000 constituents
2. Calculate ROIC = EBIT / (Net Working Capital + Net Fixed Assets)
3. Calculate Earnings Yield = EBIT / Enterprise Value
4. Rank stocks by combined ROIC + EY rank (lower combined rank = better)
5. Output top 100 candidates as a ranked table with: Ticker, Company, ROIC, EY, Combined Rank, Market Cap, Sector
6. Save results to `data/quant_gate_YYYYMMDD.csv`
7. Log the screening run to the Decision Registry

Filter out: financials, utilities, foreign ADRs, stocks under $100M market cap.

Source code: `src/investmentology/quant_gate/`
