# Data Gathering Best Practices for Investment Analysis
## What Data Matters and How to Source It

*Research completed: 2026-03-08*

---

## Executive Summary

This document synthesises what academic research and professional practice tell us about which data actually predicts future stock returns, how to source it, and how to avoid the common pitfalls that make backtests look great but live strategies fail. The core finding: most retail-accessible data is priced in; edge comes from better interpretation, combination, and quality control rather than from access to exotic sources.

---

## 1. Fundamental Data: What Actually Predicts Returns

### 1.1 The ROIC vs ROE vs ROCE Debate

**Which is most predictive?**

**ROIC (Return on Invested Capital)** is considered the gold standard among practitioners:
- Formula: NOPAT / (Debt + Equity - Cash)
- Measures how efficiently a company uses *all* the capital deployed, not just equity
- Value is created when ROIC > WACC (Weighted Average Cost of Capital); a rough benchmark is ROIC 2+ percentage points above cost of capital
- Insulates against leverage distortions (unlike ROE)

**ROE** is easier to manipulate:
- High leverage inflates ROE without creating real economic value
- A company can have strong ROE while destroying shareholder value if its cost of equity exceeds ROE
- DuPont decomposition (ROE = Net Margin × Asset Turnover × Equity Multiplier) is valuable for diagnosing *why* ROE is high or low

**ROCE (Return on Capital Employed)**:
- Uses EBIT / Capital Employed
- Avoids tax and interest distortions, making cross-country comparison easier
- Popular with UK analysts; similar to ROIC in signal quality

**Academic evidence**:
- Novy-Marx (2013, *Journal of Financial Economics*) showed **gross profitability** (Gross Profit / Assets) is a powerful predictor of future returns, even controlling for value — high-quality, profitable companies outperform despite higher prices. This is now considered a core quality factor.
- ROIC persistence (high ROIC companies tend to remain high ROIC) is well-documented: McKinsey research shows that exceptional ROIC levels fade toward industry averages over time, but the rate of fade varies by competitive moat. This fade matters — investors who pay for permanent high ROIC when it will mean-revert overpay.
- ROIC vs cost of capital spread (Economic Value Added or EVA) is the best single predictor of whether a stock deserves a valuation premium.

**Practical recommendation**: ROIC is the best single measure, but use all three to triangulate. Cross-check ROE with ROIC to detect leverage games.

---

### 1.2 Free Cash Flow Yield vs Earnings Yield

**Free Cash Flow Yield** (FCF per share / Price):
- Considered by many practitioners as superior to earnings-based metrics because:
  - Earnings can be managed through accruals; cash is harder to fake
  - FCF shows actual money available to shareholders
  - Captures capex intensity that earnings ignore
- A high FCF yield indicates a company can easily service debt and return capital; low FCF yield suggests thin returns relative to price

**Earnings Yield** (EPS / Price = inverse P/E):
- Easier to calculate and more widely available
- GAAP earnings include non-cash items, accelerated depreciation, and one-time gains/losses
- For capital-light businesses (software, asset-light services), earnings and FCF are closely aligned
- For capital-heavy industries (manufacturing, energy), FCF yield is more accurate

**Research position**: Multiple academic papers (including Fama-French extensions) show that cash-flow-based valuation metrics have stronger predictive power than earnings-based ones over 3–5 year horizons, largely because earnings are more subject to manipulation and revision.

**Practical implication**: Use normalised FCF yield (average 3-year FCF / current market cap) rather than spot FCF to smooth cyclical distortions.

---

### 1.3 Earnings Quality Metrics

**Accruals Ratio** (Sloan 1996, *The Accounting Review*):
- One of the most replicated anomalies in academic finance
- High accruals (earnings far above cash flows) predict future earnings *decreases* and below-average stock returns
- Formula: (Net Income - Operating Cash Flow) / Average Total Assets
- Companies with high accruals are more likely to experience earnings disappointments
- Signal persists for 1–3 years

**Cash Conversion Ratio**:
- Operating Cash Flow / Net Income
- Ratio > 1.0 is a positive quality signal (more cash earned than reported income)
- Ratio < 0.7 is a warning signal, especially if persistent

**Beneish M-Score**:
- Statistical model using 8 financial ratios to detect earnings manipulation probability
- Score > -1.78 suggests high manipulation probability
- Useful as a screening filter rather than standalone signal

**Piotroski F-Score**:
- 9 binary signals across profitability, leverage, and operating efficiency
- Score 0–9: score of 8+ is strong buy signal, 0–2 is strong sell/short signal
- Evidence-backed predictor of stock returns, particularly effective for value stocks

**Key point**: Earnings quality metrics are among the most actionable and least crowded retail-accessible fundamental signals.

---

### 1.4 Balance Sheet Strength Indicators

Evidence-backed metrics:
- **Net Debt / EBITDA**: < 2x generally considered manageable; > 4x signals distress risk
- **Interest Coverage** (EBIT / Interest): < 1.5x is danger zone
- **Altman Z-Score**: Composite solvency predictor; Z > 2.99 = safe, Z < 1.81 = distress
- **Current Ratio** and **Quick Ratio**: For detecting near-term liquidity risk

**Research finding**: Distressed stocks (high leverage, low coverage) underperform on a risk-adjusted basis — the "distress anomaly" — partly because of higher bankruptcy risk and partly because institutional investors are constrained from holding them.

---

### 1.5 Revenue Quality Indicators

**Recurring vs one-time revenue**:
- Subscription/SaaS revenue commands premium multiples because it is predictable
- Metrics: Net Revenue Retention (NRR), Annual Recurring Revenue (ARR) growth, churn rate
- NRR > 120% = strong signal of product-market fit and upsell effectiveness

**Revenue concentration risk**:
- Single customer > 10% of revenue = material risk flag
- Geographic concentration in high-risk regions = discounting factor

**Revenue recognition patterns**:
- Watch for revenue pulled forward (large receivables spikes)
- Deferred revenue increases = positive (cash collected ahead of recognition)

---

### 1.6 Capital Allocation Track Record

This is qualitative but measurable:
- **Share buyback efficiency**: Were buybacks done at reasonable prices? Use FCF yield at time of buyback
- **M&A track record**: Goodwill impairments signal poor acquisition discipline
- **Dividend sustainability**: FCF payout ratio > 100% is unsustainable
- **ROIC on incremental capital**: Does the company earn high returns on *new* capital? Regression of capex vs subsequent revenue/profit growth answers this

**Insider ownership**: Founder-led companies with 10–20%+ insider ownership tend to outperform. Ownership thresholds that matter:
- > 5%: Meaningful economic alignment
- > 10%: Strong alignment, less likely to dilute shareholders
- > 20%: Management prioritises long-term value; potential for illiquidity discount
- Over 50%: Control issues, risk of not acting in minority shareholder interest

---

## 2. Insider and Institutional Signals

### 2.1 SEC Form 4 Analysis

**What it is**: Filed within 2 business days of any transaction by directors, officers, or >10% shareholders. Types of transactions:
- Purchases in open market (most bullish signal)
- Option exercises followed by holds (moderately bullish)
- Option exercises followed by immediate sales (generally neutral — just compensation vesting)
- Open market sales (moderately bearish, but weaker signal than buys since insiders sell for many reasons)

**High-conviction signals**:
- **Cluster buys**: Multiple insiders buying within a short window. Research shows cluster buys generate 3–5% abnormal returns over 6 months.
- **CEO/Director open market purchases with no planned trading history**: Highest conviction signal — insiders rarely buy unless they believe price is attractive
- **Buying after a significant price decline**: Insiders buying into weakness is among the strongest signals available
- **Large size relative to salary**: A CFO buying $500K of stock on a $300K salary is material

**Weak/misleading signals**:
- Option exercises (compensation, not market view)
- 10b5-1 plan sales (pre-scheduled, no incremental information)
- Routine small purchases
- Insider selling during high-price periods (may just be diversification)

**Data source**: EDGAR (SEC.gov/EDGAR) — free, typically available within 2 days. Third-party aggregators like OpenInsider.com, Finviz, Guru Focus provide screening tools.

---

### 2.2 13F Filing Analysis

**What it is**: Quarterly filing by institutional managers with >$100M AUM, disclosing long equity positions. Filed 45 days after quarter end.

**Critical limitations**:
- Only shows **long equity positions** (no shorts, bonds, derivatives, or non-US securities)
- **45-day delay** means data is stale by 60–135 days by the time it's usable
- Hedge funds often use 13F positions as decoys while real returns come from shorts
- Managers file as late as possible to minimise signal leakage

**What's useful**:
- **Concentration**: High-conviction positions (top 5–10 holdings) of respected fundamental managers (Baupost, Pershing Square, Third Point)
- **New positions**: Stocks appearing for first time in a high-quality fund's 13F deserve investigation
- **Exits**: Complete positions being sold is a neutral-to-negative signal
- **Activist positions (Schedule 13D)**: Filed when any entity acquires > 5% of stock; often a catalyst signal

**Hedge fund crowding risk**: When multiple funds own the same stocks, any de-risking triggers cascading sell pressure. The "crowded trade" phenomenon is well-documented and leads to sharp drawdowns in popular hedge fund names. Track crowding via Goldman Sachs "VIP List" or similar.

**13F as a screen, not a trade**: Best used to generate names for independent research, not to blindly copy.

---

### 2.3 Institutional Ownership Dynamics

**Ownership concentration effects**:
- Stocks moving from low institutional ownership to higher ownership see price appreciation as the "discovery" phase plays out
- Stocks with very high institutional ownership face limited new buyers; risk is concentrated exits
- Index inclusion events create predictable buying pressure; deletion from indices creates selling pressure

**Smart money vs dumb money**:
- Long-horizon fundamental hedge funds (Baupost, Marathon Asset Management) have better track records than momentum/quant funds
- Mutual fund managers on average underperform indices after fees

---

## 3. Sentiment Data with Predictive Value

### 3.1 News NLP: Beyond Positive/Negative

**Simple sentiment is too simple**: Standard positive/negative scoring on news has been largely arbitraged away. What has residual value:

**Uncertainty language detection**:
- Companies using hedge words ("may," "could," "we believe") in forward-looking statements signal lower earnings predictability
- NLP models trained to detect uncertainty in MD&A sections are predictive of earnings volatility
- Words like "uncertain," "challenging," "headwinds" in management commentary correlate with subsequent underperformance

**Forward guidance analysis**:
- Companies explicitly narrowing guidance ranges signal increased management confidence
- Companies withdrawing guidance ("too uncertain to forecast") have higher subsequent volatility
- Upward revisions to guidance are stronger bullish signals than initial high guidance

**Tone shifts over time**:
- LLM-based analysis of sequential earnings call transcripts for tone shifts (more/less defensive, more/less optimistic) is more predictive than point-in-time analysis
- Management becoming evasive or short in responses to analyst questions is a warning sign

**Word frequency patterns (academic evidence)**:
- Loughran and McDonald (2011, *Journal of Finance*) showed that financial-domain sentiment dictionaries far outperform general-purpose sentiment word lists (like Harvard Psychosociological Dictionary)
- "Uncertainty," "litigious," and "modal" word categories are predictive beyond simple positive/negative

---

### 3.2 Earnings Call Transcript Analysis

**What analysts look for**:
- **Q&A tone**: Management terseness or defensiveness on key metrics
- **Guidance specificity**: Quantitative guidance vs vague qualitative commentary
- **Language consistency**: Deviation from prior quarter's language is meaningful
- **Customer, product, geography mentions**: Sudden changes in what's highlighted vs de-emphasised

**Linguistically predictive patterns (research-backed)**:
- Use of first-person plural "we" vs passive voice ("revenue declined") — passive voice deflects accountability
- Long answers to simple questions = management trying to talk past a problem
- Short answers to complex questions = management dismissing legitimate concerns
- Specific, quantitative future projections = higher confidence

**Sources for transcripts**:
- SEC EDGAR (8-K filings after earnings releases, but no structured transcript)
- Seeking Alpha earnings call transcripts (free with delay, paid for immediate)
- Motley Fool Transcripts
- Refinitiv (expensive)
- FactSet (expensive)

---

### 3.3 Social Media: Signal vs Noise

**WallStreetBets / Reddit (r/stocks, r/investing)**:
- Retail-driven. Short-term (hours to days) price impact documented for small/micro caps
- Longer-term, Reddit momentum is negative: stocks that spike on Reddit sentiment tend to reverse within 4–6 weeks
- **Not useful** for fundamental investment decision-making
- **Watch for**: Coordinated short squeezes can create brief trading windows but are speculative

**StockTwits**:
- More trader-focused than fundamental-focused
- Sentiment extremes (very high bull %) have contrarian value for short-term mean reversion
- Schoar and Sunderesan research shows retail options flow (detectable via unusual options activity) sometimes precedes earnings surprises

**What actually has value**:
- Abnormal social media volume + unusual options activity simultaneously: warning of potential earnings surprise or corporate event
- Negative Glassdoor sentiment decline correlates with future earnings misses (management culture degradation signals)

---

### 3.4 Options-Based Sentiment

**Put-Call Ratio**:
- Calculated: Number of Put Options / Number of Call Options traded
- Equity average baseline: ~0.7 (more calls than puts normally)
- Ratio > 1.0 = notably bearish sentiment; contrarian buy signal at extremes
- Ratio approaching 0.5 = notably bullish; contrarian caution signal
- More useful as a contrarian indicator at extremes than as a trend-following indicator
- Equity P/C ratio (as opposed to index P/C) more useful for individual stock analysis

**VIX Term Structure**:
- VIX measures 30-day implied volatility; VIX9D measures 9-day; VIX3M measures 3-month
- **Contango** (near-term VIX < long-term VIX): Normal environment, fear dissipating
- **Backwardation** (near-term VIX > long-term VIX): Acute stress; market pricing near-term disaster
- Extreme backwardation followed by normalisation has historically been a buy signal within 3–6 months

---

## 4. Macro and Sector Signals

### 4.1 Yield Curve as Leading Indicator

**Most reliable signal**: 10-year minus 2-year Treasury spread (2s10s)
- **Inverted** (negative): Historically preceded every US recession since 1975, with false positive in mid-1960s
- Typical lead time: 6–24 months before recession begins
- **Fed Chair Powell's preferred measure**: Current 3-month yield vs market-implied 3-month rate 18 months forward

**10-year minus 3-month spread** (academic favourite):
- Slightly more predictive than 2s10s in academic literature
- Cleveland Fed maintains recession probability estimates based on this spread

**Investment implications**:
- Inverted curve: Reduce cyclical exposure, increase defensive/quality tilt
- Steep curve (10yr - 2yr > 2%): Expansionary environment favours small caps, cyclicals, financials
- Flattening but not yet inverted: Late-cycle, favour quality and defensive growth

---

### 4.2 Credit Spread Dynamics

**What credit spreads tell equity investors**:
- **Investment grade (IG) OAS** (Option-Adjusted Spread): Spread over Treasuries for BBB/A rated corporate bonds
- **High yield (HY) spread**: Spread over Treasuries for below-investment-grade bonds
- **Key signal**: HY spread widening > 200bps from cycle lows is a warning sign for equity markets; > 500bps suggests distress/recession environment

**Leading vs lagging**:
- Credit markets often price stress before equity markets because credit investors focus on solvency; equity investors focus on growth
- HY credit deterioration often precedes equity bear markets by 3–6 months
- IG spreads widening is an earlier, more sensitive warning signal

**Sources**: FRED (Federal Reserve Economic Database) — free, has IG and HY spread series (BofA indexes).

---

### 4.3 Sector Rotation (Business Cycle Framework)

The business cycle approach (Fidelity, PIMCO, others):

| Cycle Phase | Outperforming Sectors | Lagging Sectors |
|-------------|----------------------|-----------------|
| Early recovery | Consumer Discretionary, Financials, Industrials | Utilities, Healthcare |
| Mid cycle | Information Technology, Industrials | Energy, Materials |
| Late cycle | Energy, Materials, Healthcare | Consumer Discretionary |
| Recession | Utilities, Consumer Staples, Healthcare | Financials, Consumer Disc |

**Evidence caveats**:
- Cycle phases are only identifiable in hindsight
- Transition periods are messy and often last longer than expected
- Sector rotation signals have shortened lead times as market participants try to front-run them

**Leading Economic Indicators (LEI)** that actually lead:
- **ISM Manufacturing PMI**: Sub-50 = contraction, > 55 = strong expansion
- **JOLTS Job Openings**: Leads employment by 2–3 quarters
- **Building Permits**: Leading indicator for construction and related sectors
- **Consumer Confidence** (Conference Board): Leads retail spending
- **Initial Jobless Claims** (weekly): Fastest-refreshing labour market indicator
- **Yield curve** (as above)
- **Stock prices themselves**: Part of the Conference Board LEI

---

### 4.4 Currency Impacts on Multinational Earnings

**Practical rules**:
- US companies with high international revenue are exposed to USD strengthening (USD strong = headwind to reported earnings)
- A 10% USD appreciation typically reduces S&P 500 earnings by 2–3% given ~40% international revenue mix
- Translation effect (reporting foreign earnings in USD) vs transaction effect (actual cash flows) — translation is mechanical, transaction is the real economic effect
- **Hedge indicator**: Companies that actively hedge currency exposure (disclosed in 10-K) have smoother earnings; unhedged companies have more volatile near-term earnings

---

### 4.5 Commodity Price Transmission

Key commodity-sector relationships:
- **Oil price** → Energy sector direct; airlines, chemicals, transportation indirect negative; energy-producing countries' currencies
- **Copper price** → "Dr. Copper" as economic leading indicator; copper demand correlates with industrial activity; positive for mining stocks, negative for copper-intensive manufacturers
- **Steel/Iron ore** → Steel producers, auto manufacturers, construction equipment
- **Agricultural commodities** → Food processors, fertiliser companies, consumer staples

**Sourcing commodity data**: FRED, CME Group, World Bank commodity price data (all free).

---

## 5. Technical Indicators with Academic Evidence

### 5.1 What Has Empirical Support

**Momentum (12-month, skip 1 month)**:
- Most robustly documented market anomaly
- Buy past 12-month winners (excluding last month), sell past losers
- Jegadeesh and Titman (1993) originally documented; replicated globally
- Works across asset classes (stocks, bonds, currencies, commodities)
- Holding period: 3–12 months optimal; reversal sets in beyond 12 months
- **Risk**: Momentum crashes during market reversals (2009, 2020 recovery). Momentum combined with low volatility reduces crash risk.

**52-week high proximity**:
- Stocks near their 52-week high outperform, even controlling for past 12-month return
- Behavioural explanation: anchoring to prior high creates resistance at that level, then breakout accelerates

**Relative Strength**:
- Cross-sectional momentum: stocks that have outperformed sector peers continue to outperform near-term
- Useful as a confirmation signal when combined with fundamental analysis

**Moving Averages (limited but real evidence)**:
- 200-day MA as market regime filter: being in a stock while it is above its 200-day MA and out when below reduces drawdowns without proportionate return sacrifice
- Evidence is stronger for market-level timing than for individual stock selection
- Execution is difficult — whipsawing in sideways markets erodes returns

**RSI (Relative Strength Index)**:
- RSI > 70 = overbought; RSI < 30 = oversold
- Used primarily as a mean-reversion signal for short-term traders
- Academic evidence for RSI predictiveness is mixed; works better in combination with other signals than standalone
- RSI divergences (price making new high while RSI makes lower high) have some evidence for predicting pullbacks

**Volume-Price Divergence**:
- Price rising on declining volume = suspect strength; potential reversal
- Price declining on declining volume = potential exhaustion of selling
- On-Balance Volume (OBV) tracks cumulative buying vs selling pressure

---

### 5.2 Technical + Fundamental Combination

**Research shows**: Combining value/quality fundamentals with momentum signals generates better risk-adjusted returns than either alone:
- **High quality + positive momentum**: Outperforms both factors individually
- **Deep value + negative momentum**: Avoid despite cheap valuation (falling knives)
- **Expensive growth + strong momentum**: More risk than reward in later stages
- AQR's "Quality Minus Junk" and similar strategies build on this

**Mean reversion timescales**:
- Very short-term (1–5 days): Mean reversion tendency (short-term overreaction)
- Medium-term (1–12 months): Momentum tendency (continuation)
- Long-term (3–5 years): Value reversion (expensive underperforms, cheap outperforms)

---

## 6. Data Quality and Validation

### 6.1 Critical Biases to Eliminate

**Survivorship Bias**:
- Using only currently-existing companies in historical analysis inflates returns
- If you test a strategy on the S&P 500 constituents *today*, you're only testing stocks that survived — the ones that went bankrupt or were delisted are excluded
- **Fix**: Use point-in-time constituent databases (expensive from Bloomberg/Refinitiv; partially available via Ken French Data Library and CRSP)
- For retail research: acknowledge the limitation; use broad universe datasets

**Look-Ahead Bias**:
- Most insidious backtesting error: using data that was not available at the time of the hypothetical trade
- Example: Using Q4 earnings data to construct a portfolio dated Jan 1, when Q4 earnings are actually released in February
- **Fix**: Always align data to filing/release dates, not period dates
- Financial statements use the *period end date* but are only *published* 30–60 days later (10-K: 60–90 days; 10-Q: 40–45 days)

**Point-in-Time Data**:
- Financial data gets restated over time; databases that store only the latest version of financials create look-ahead bias
- True point-in-time databases (Bloomberg, Compustat with point-in-time flag) preserve what was actually available at each date
- For retail use: yfinance does NOT provide point-in-time data; SEC EDGAR provides original filings which are point-in-time

**Selection Bias in backtests**:
- Data mining: testing many variations and reporting only the best
- Rule of thumb: Require out-of-sample validation; if a strategy works on US equities 1990–2010, does it work on European equities or 2010–2024?

---

### 6.2 Data Staleness and Conflicting Sources

**Professional system approach**:
- **Freshness indicators**: Tag each data point with source, last-updated timestamp, and expected refresh frequency
- **Confidence scoring**: Lower confidence for stale data; weight signals by recency
- **Source hierarchy**: Primary sources (SEC filings, exchange data) > secondary aggregators > derived calculations
- **Conflict resolution**: When two sources disagree, defer to primary source; flag for investigation

**Common conflict scenarios**:
- Adjusted vs unadjusted prices (splits, dividends): Always use total return data for performance calculation
- GAAP vs non-GAAP earnings: Analyse both, weight GAAP for fundamental consistency
- Trailing vs forward earnings: Trailing is certain, forward is estimate; label clearly

---

### 6.3 Data Provider Comparison

| Provider | Cost | Strengths | Limitations |
|----------|------|-----------|-------------|
| **Bloomberg Terminal** | ~$25K/year | Comprehensive, real-time, excellent fixed income | Cost; primarily institutional |
| **Refinitiv (LSEG)** | ~$20K/year | Strong on news/sentiment; good fundamental data | Complex UI; expensive |
| **FactSet** | ~$15K/year | Good point-in-time data; strong for fundamentals | Less real-time data |
| **Morningstar** | $200–$2K/year | Strong on mutual fund data; good fundamental screening | Less granular alternatives |
| **yfinance** | Free | Price/OHLCV data, basic fundamentals | Not point-in-time; ToS prohibits commercial use; unreliable data quality |
| **SEC EDGAR (XBRL)** | Free | Primary source for all SEC filings; point-in-time | Raw/unstructured; requires parsing |
| **FRED** | Free | Comprehensive macro/economic data | No equity-level data |
| **Alpha Vantage** | Free/$50/mo | OHLCV, technical indicators, basic fundamentals | Rate limited on free tier; data quality issues on some feeds |
| **Polygon.io** | Free/$29/mo | Good OHLCV and options data; reliable REST API | Fundamental data limited on free tier |
| **IEX Cloud** | Free/$9/mo | Clean OHLCV; good for small portfolios | Less comprehensive than paid providers |
| **Quandl/Nasdaq Data Link** | Free/paid | Good alternative datasets; strong macro | Many datasets now require paid subscription |

---

## 7. Accessible Data Sources for Retail Investors

### 7.1 Free and Low-Cost Data APIs

**Price and Market Data**:
- **yfinance** (Python): `pip install yfinance` — easiest to use; covers OHLCV, basic fundamentals, insider transactions. Not point-in-time; terms of service restrict commercial use. Version 1.2.0 (2026).
- **Alpha Vantage** (free tier: 25 requests/day, 500/day on paid): Covers time series, technical indicators, forex, crypto, economic indicators. API key required.
- **Polygon.io** (free tier available): Real-time and historical price data, options data, news. REST and WebSocket. More reliable than yfinance for production systems.
- **IEX Cloud** (free tier available): Market data, financials, news. Acquired by Intercontinental Exchange (ICE); good documentation.

**Fundamental Data**:
- **SEC EDGAR XBRL API**: All SEC-filed financial data in structured format. Free. Endpoint: `https://data.sec.gov/api/xbrl/`. Provides GAAP financials with original filing dates — genuinely point-in-time.
- **Simfin** (free with attribution): Structured fundamental data from SEC filings. Good for fundamental screening.
- **Financial Modeling Prep** (FMP): Free tier with basic financials; paid for full coverage.

**Macro Data**:
- **FRED API** (St. Louis Fed): 500,000+ economic time series. Free. Python library: `fredapi`. Covers interest rates, yield curves, credit spreads, employment, inflation, GDP components.
- **Bureau of Economic Analysis (BEA) API**: GDP, personal income, corporate profits. Free.
- **Bureau of Labor Statistics (BLS) API**: Employment, CPI, PPI. Free.
- **OECD Data API**: International macro data. Free.

**Insider and Institutional Data**:
- **SEC EDGAR Form 4 feeds**: Real-time RSS feed for Form 4 filings. Free.
- **OpenInsider.com**: Free web scraping target or use their API for insider transaction data aggregated from EDGAR.
- **SEC EDGAR 13F filings**: Free; parse quarterly holdings files at `https://www.sec.gov/cgi-bin/browse-edgar`.
- **WhaleWisdom** (limited free tier): Aggregated 13F data with sorting/filtering.

**Options Data**:
- **CBOE**: Free delayed options data, VIX series, put-call ratios.
- **Unusual Whales**: Retail-accessible unusual options flow data.

**Sentiment and News**:
- **Finviz**: Free for basic news sentiment; paid for more.
- **The Transcript** (subscription): Curated earnings call highlights.
- **Seeking Alpha Earnings Call Transcripts**: Free with ads.

---

### 7.2 Web Scraping Sources with Signal Value

**Earnings Whispers** (earningswhispers.com):
- Unofficial "whisper numbers" vs consensus estimates
- When the whisper number significantly exceeds consensus, buy-side expectations are higher than sell-side models
- Stocks that beat both consensus and whisper tend to have stronger post-earnings moves

**Glassdoor and Indeed**:
- Employee satisfaction declining YoY correlates with business problems before they appear in financials
- CEO approval rating decline is an early warning signal for management dysfunction
- Methodology: track sentiment scores for companies you hold, flag > 10% year-over-year decline

**Job Postings (LinkedIn, Indeed)**:
- Rapid increase in engineering/product job postings = expansion signal
- Sudden hiring freeze or job posting deletions = potential contraction/pivot
- Workforce analytics companies (Thinknum, Revelio Labs — expensive) systematise this

**Import/Export Data (Census Bureau)**:
- Monthly trade data reveals supply chain trends
- Useful for industrials, materials, consumer goods companies with complex supply chains

---

### 7.3 Building a Comprehensive Budget Data Pipeline

**Tier 1 (Free, essential)**:
- yfinance for price history and basic fundamentals (accept quality limitations)
- SEC EDGAR for primary SEC filings (10-K, 10-Q, Form 4, 13F)
- FRED for all macroeconomic series
- CBOE for VIX and put-call ratio data

**Tier 2 ($50–$200/month, significant upgrade)**:
- Polygon.io Starter: Better OHLCV reliability, options data
- Alpha Vantage Premium: More API calls, fundamentals
- Financial Modeling Prep: Structured fundamental data, SEC filing parser

**Tier 3 ($500+/month, professional quality)**:
- Tiingo: High-quality fundamental data with point-in-time support
- EOD Historical Data: Good coverage, international markets
- Intrinio: Granular financial data

**Avoid**: Data scraped from sites that prohibit it in their ToS (risk of legal action + data quality issues); any provider claiming real-time data at implausibly low cost.

---

### 7.4 Data Validation Framework

For any data pipeline, apply these validation checks:
1. **Completeness**: Is there data for all expected tickers in the universe?
2. **Freshness**: When was each field last updated? Is it within expected refresh window?
3. **Sanity bounds**: Price > 0; P/E between 1–1000 for most normal businesses; ROIC between -100% and +200%
4. **Consistency**: Do revenue figures in income statement match cash flow statement?
5. **Cross-source reconciliation**: Spot-check key figures against SEC primary filing
6. **Corporate actions**: Are splits and dividends correctly applied to price history?

**Automation**: Build a data quality monitor that alerts when values fall outside expected ranges or when staleness exceeds thresholds.

---

## 8. What Data is Interesting vs Actionable

### Actually Actionable (evidence-backed, accessible)

| Signal | Horizon | Strength | Accessibility |
|--------|---------|----------|---------------|
| ROIC > WACC spread | 1–3 years | High | Free (calculate from EDGAR) |
| Accruals ratio (Sloan) | 1–2 years | High (replicated) | Free (calculate from EDGAR) |
| Piotroski F-Score | 1 year | Moderate-High | Free (calculate) |
| Insider cluster buys (open market) | 3–6 months | Moderate | Free (EDGAR/OpenInsider) |
| Price momentum (12m-1m) | 3–12 months | High (robust) | Free (price data) |
| FCF yield (normalised) | 1–3 years | Moderate-High | Free (calculate) |
| Yield curve (2s10s) | 6–24 months | High for recession | Free (FRED) |
| ISM PMI trend | 2–4 quarters | Moderate | Free (ISM.org) |
| Options P/C ratio extremes | 1–4 weeks | Moderate (contrarian) | Free (CBOE) |

### Interesting but Low Actionability

| Signal | Why Low Actionability |
|--------|----------------------|
| Glassdoor sentiment | Signal too noisy, too slow; hard to act before price moves |
| Job posting trends | Requires systematic aggregation; public sources lag |
| Reddit/StockTwits sentiment | Too short-term; noise > signal for fundamental investors |
| 13F mimicking | Too stale by the time data is available |
| Individual earnings call tone | Requires consistent methodology; easy to over-interpret |

### Dangerous (creates false confidence)

- **Simple P/E valuation alone**: No sector context, no quality adjustment, no growth consideration
- **Price targets from analysts**: Strong conflict of interest; coverage initiation bias
- **TV/media sentiment**: Predominantly noise; designed to entertain, not inform
- **Overfitted backtests**: Strategy works perfectly on historical data because it was optimised on that data

---

## Key Conclusions

1. **ROIC is the best single fundamental metric** but must be compared to cost of capital, not used in isolation. Gross profitability (Novy-Marx) is a close second with strong academic support.

2. **Earnings quality matters more than earnings level**: High accruals predict disappointment regardless of reported EPS. Cash conversion is more reliable than net income.

3. **Insider buying (open market, cluster) is the highest-signal free data point** for retail investors. Ignore option exercises and 10b5-1 sales.

4. **13F data is structurally compromised** for direct mimicking (stale, no shorts) but useful for idea generation.

5. **Momentum is real but has dangerous reversals**: Use 12-month momentum as a confirmation signal; combine with quality/value, not as a standalone strategy.

6. **The yield curve and credit spreads are macro leading indicators** that retail investors almost entirely ignore; monitoring them improves portfolio timing.

7. **Free data is sufficient** for fundamental analysis. EDGAR XBRL provides point-in-time fundamentals. FRED provides all macro data needed. The main gap is data quality, not availability.

8. **Survivorship bias and look-ahead bias will destroy any backtest** that doesn't account for them. EDGAR XBRL solves look-ahead bias for fundamentals if you use the filing date, not the period date.

9. **Sentiment data has short-term value at extremes** (VIX backwardation, extreme P/C ratios as contrarian signals) but limited value for fundamental decision-making.

10. **Alternative data (Glassdoor, job postings, satellite, credit card)** is genuinely predictive but is expensive, legally complex, and institutionally crowded — retail alpha from it is limited.

---

*Sources: Investopedia, SEC EDGAR documentation, Alpha Vantage API docs, FRED categories, AQR research summaries, yfinance PyPI documentation, academic research synthesis (Sloan 1996, Jegadeesh-Titman 1993, Novy-Marx 2013, Loughran-McDonald 2011, Fama-French factor research).*
