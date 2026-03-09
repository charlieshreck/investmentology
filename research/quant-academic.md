# Quantitative and Academic Approaches to Stock Assessment

*Research compiled: 2026-03-08*

---

## 1. Factor Models

### 1.1 Capital Asset Pricing Model (CAPM) — The Foundation

Before factor models, the CAPM (developed in the 1960s) held that a single factor — market beta — explained all variation in expected returns. The expected return formula:

```
E[r] = Rf + β(Rm - Rf)
```

Empirical tests showed this was too simple: the risk-return relationship was far too flat. Small stocks and value stocks consistently outperformed what CAPM predicted, leading to the Fama-French revolution.

---

### 1.2 Fama-French Three-Factor Model (1992–1993)

Eugene Fama and Kenneth French published foundational papers showing CAPM left substantial return variation unexplained. They added two factors to market beta:

**Formula:**
```
r = Rf + β(Rm - Rf) + bs·SMB + bv·HML + α
```

**Three Factors:**
- **Market** (MKT): Excess return of market over risk-free rate
- **SMB** (Small Minus Big): Small-cap premium — historically small companies outperform large companies over long periods
- **HML** (High Minus Low): Value premium — high book-to-market (value) stocks outperform low book-to-market (growth) stocks

**Key findings:**
- The three-factor model explains over 90% of diversified portfolio returns, vs ~70% for CAPM
- Factors are country-specific; local factors provide better explanation than global factors
- Works across US, Europe, Japan, Asia-Pacific, and emerging markets

**Data access:** Kenneth French's website (mba.tuck.dartmouth.edu) provides free historical factor data, the standard academic resource.

**Criticism:** Does not include momentum, which is empirically important. HML becomes partially redundant in the five-factor model.

---

### 1.3 Carhart Four-Factor Model (1997)

Mark Carhart added a **momentum factor (MOM)** to the three-factor model. Momentum is long prior-year winners, short prior-year losers (typically 12-month return excluding most recent month).

**Why momentum matters:**
- Jegadeesh and Titman (1993) documented momentum in US stocks
- AQR research confirmed "Value and Momentum Everywhere" — both premia exist across eight diverse asset classes (equities, bonds, currencies, commodities)
- Value and momentum are negatively correlated with each other, providing diversification benefit
- The combined value+momentum portfolio has a high Sharpe ratio and strong global funding liquidity as a partial source

**Practical use:** Momentum is one of the most robust and widely replicated factors. The 12-1 month lookback (12-month return, skip most recent month) is standard.

---

### 1.4 Fama-French Five-Factor Model (2015)

In 2015, Fama and French extended to five factors, adding:

- **RMW** (Robust Minus Weak): **Profitability factor** — firms with high operating profitability outperform firms with low operating profitability
- **CMA** (Conservative Minus Aggressive): **Investment factor** — firms that invest conservatively outperform firms that invest aggressively

**Key implication:** Adding RMW and CMA makes HML largely redundant in the US (CMA has 0.7 correlation with HML). However, academics debate whether HML retains information internationally.

**What "profitability" means in practice:**
- Operating profitability = (Revenue - COGS - SG&A - interest expense) / book equity
- High-profitability firms are quality businesses generating strong returns on equity

**What "investment" means:**
- Conservative investment = low total asset growth year-over-year
- Aggressive investment (acquisitions, capex, share issuance) is associated with lower subsequent returns — the "investment anomaly"

---

### 1.5 The Q-Factor Model (Hou, Xue, Zhang)

The q-factor model (2015) provides an alternative theoretical framework to Fama-French, grounded in investment-based asset pricing:

- **Market factor** (MKT)
- **Size** (ME): Market equity
- **Investment** (I/A): Asset growth — conservative investment outperforms
- **Profitability** (ROE): Return on equity — high ROE outperforms

The key insight from the q-theory is that both investment and profitability factors arise naturally from the firm's optimization problem: firms with high investment have high prices (low expected returns); firms with high profitability have high prices but also high expected returns.

**Why it matters:** The q-model provides a rational (non-behavioural) explanation for factor premia grounded in corporate finance theory.

---

### 1.6 Do Factor Premiums Persist? Recent Research (2023-2026)

**The case for persistence:**
- AQR's "Value and Momentum Everywhere" dataset is updated through December 2025, showing continued premia
- Bridgewater's All Weather strategy (launched 1996) is built on the principle that asset class returns reflect structural economic relationships that persist through regimes
- AQR research on "Hold the Dip" (Dec 2025) shows trend-following (momentum) consistently beats market timing
- Risk-based explanations: if premia compensate for real economic risk (recession, liquidity), they should persist because rational investors require compensation

**The case against persistence / critics:**
- Rob Arnott, Campbell Harvey (2019): many reported factors result from data mining, not genuine economic effects. Of hundreds of proposed factors, only a small subset show statistically significant and persistent out-of-sample performance
- Factor crowding: popular factors attract large investor flows, driving up valuations and lowering future returns. This is particularly relevant post-2010 as factor ETFs proliferated
- Patton and Weller (2020): trading costs and market frictions erode theoretical returns, especially for high-turnover factors
- The value factor significantly underperformed from ~2017-2020, leading to debate about whether it was "dead"
- A 2025 academic paper noted that factor investing research often confuses correlation and causation

**Practical takeaway for retail investors:**
- Core factors (value, momentum, quality/profitability, low volatility) have the longest out-of-sample track records
- Factor premiums are cyclical; factor timing is difficult and usually counterproductive
- Diversifying across multiple uncorrelated factors is more robust than betting on any single factor
- Transaction costs matter: momentum requires higher turnover than value; net-of-cost returns shrink significantly

---

### 1.7 The Quality Factor (QMJ — Quality Minus Junk)

AQR's quality factor research (Asness, Frazzini, Pedersen) defines quality companies as those that are:
1. **Profitable**: high gross profits/assets, ROE, ROA, cash flow/assets
2. **Growing**: positive earnings growth, sustainable profitability
3. **Safe**: low beta, low financial leverage, low earnings variability, low credit risk
4. **Well-governed**: low accruals (earnings quality), low payout dilution

High-quality stocks command premium valuations but still provide excess returns relative to risk — challenging simple risk-based explanations. Quality is negatively correlated with value (cheap stocks are often low quality), but combining quality + value creates a powerful "high quality at a reasonable price" screen.

---

## 2. Quantitative Fund Approaches

### 2.1 AQR Capital Management

AQR (founded by Cliff Asness, former PhD student of Eugene Fama) systematizes academic factor research at scale:

**Core philosophy:**
- Diversify across many uncorrelated return sources (factors)
- Be systematic and rules-based to remove behavioural biases
- Combine value, momentum, quality, and carry across all asset classes, not just equities
- Long/short implementations capture factor premia more purely than long-only

**Key published frameworks:**
- **Value + Momentum Everywhere**: Consistent premia across equities, bonds, FX, commodities. The combination has higher Sharpe than either alone because they are negatively correlated (when value is cheap/suffering, momentum tends to be working)
- **Quality Minus Junk**: Long quality, short low-quality businesses
- **Betting Against Beta**: Low-beta stocks outperform high-beta stocks on a risk-adjusted basis (investors over-pay for lottery-like high-beta exposure)
- **Active Extension (130/30)**: Long-short framework allowing skilled managers to short unattractive stocks. More efficient than long-only for capturing factor alpha
- **Trend Following**: Momentum applied cross-asset; "Buy the Dip" consistently underperforms trend-following (Dec 2025 research)

**What retail investors can adapt:**
- Multi-factor screening: score stocks on value (P/B, P/E, EV/EBITDA), momentum (12-1 month return), and quality (ROE, low debt, earnings stability)
- Combine factors; avoid concentrated bets on single factors
- Accept that factor performance is cyclical — don't abandon after 2-3 years of underperformance

---

### 2.2 Bridgewater Associates — The Economic Machine

Ray Dalio's core insight (developed post-Nixon shock 1971): any market surprise can be decomposed into shifts in:
1. **Economic growth** (rising/falling relative to expectations)
2. **Inflation** (rising/falling relative to expectations)

**The economic machine framework:**
- The economy runs in cycles driven by productivity growth (long-term), short-term credit cycles (~5-8 years), and debt cycles (~75 years)
- Credit expansion drives short-term booms; credit contraction drives recessions
- Central bank policy (interest rates, printing money) responds predictably to these cycles
- Asset prices move based on **surprises relative to what's priced in**, not absolute conditions

**All Weather / Risk Parity:**
```
Portfolio return = cash + beta + alpha
```
All Weather holds assets balanced by their **risk contribution** across four economic environments:
- Growth rising + Inflation rising → commodities/gold outperform
- Growth rising + Inflation falling → equities/credit outperform
- Growth falling + Inflation rising → inflation-linked bonds, gold
- Growth falling + Inflation falling → nominal bonds

**What retail investors can adapt:**
- Economic regime detection (PMI, credit spreads, inflation breakevens) for tactical positioning
- Risk-budget portfolios: equal risk, not equal capital, across asset classes
- Debt cycle analysis for identifying major turning points (credit creation, leverage ratios)

---

### 2.3 Two Sigma — Data Science Approach

Two Sigma applies systematic machine learning across thousands of data sources:

**Philosophy:**
- Markets are information processing machines; alpha comes from processing information faster or better
- No single signal is reliable; combine hundreds of weak signals
- Rigorous statistical testing to distinguish real signals from noise
- Massive infrastructure for data ingestion, cleaning, and feature engineering

**Approach elements:**
- Systematic cross-sectional stock selection using ML models
- Alternative data integration at scale (satellite, transactions, web data)
- Continuous model improvement as market microstructure evolves
- Strong emphasis on avoiding overfitting through out-of-sample testing

**What retail investors can adapt:**
- The principle of combining many weak, diverse signals is sound at any scale
- Python/pandas/sklearn are sufficient to implement systematic screens
- Focus on signals with economic intuition, not pure data mining

---

### 2.4 D.E. Shaw — Mathematical Arbitrage

D.E. Shaw pioneered:
- **Statistical arbitrage**: Mean reversion across hundreds of correlated stock pairs
- **Multi-factor quantitative models** combining fundamental and technical signals
- **High-frequency trading** infrastructure

Their edge at retail scale is not replicable (microsecond execution, co-location, proprietary data). However, the statistical methodology is:
- Identify pairs/groups of stocks with structural economic linkages
- Model the expected spread and trade mean reversion
- Use rigorous position sizing based on signal confidence and volatility

---

## 3. Alternative Data in Practice

### 3.1 What Is Alternative Data?

Alternative data refers to non-traditional data sources that provide insight into company performance before it appears in official filings. Key characteristics:
- Produced as a **by-product** of business operations, not intentionally published
- Often high-frequency (daily, even real-time)
- Requires significant processing to extract investment-relevant signal

### 3.2 Key Alternative Data Types

**Geolocation / Foot Traffic:**
- Satellite imagery of parking lots (retail stores, factories, oil storage)
- Mobile phone location data (store visits, customer counts)
- Used to nowcast same-store sales before earnings releases
- *Retail accessibility*: Services like Placer.ai, SafeGraph provide foot traffic data; costly but available

**Credit / Debit Card Transactions:**
- Aggregated consumer spending by merchant/sector
- Provides near-real-time revenue estimates for consumer companies
- *Sources*: Second Measure, Earnest Analytics, Affinity Solutions
- *Retail accessibility*: Expensive; some data is partially available through financial data providers

**Web Scraping:**
- **Job postings**: Rising headcount signals growth; hiring in specific roles (AI engineers) reveals strategy. LinkedIn, Indeed, Glassdoor data
- **Pricing data**: E-commerce price tracking reveals demand and competitive dynamics
- **Product reviews / ratings**: Glassdoor employee ratings correlate with management quality
- **Online retail rankings**: Amazon BSR (Best Seller Rank) reveals sales velocity
- *Retail accessibility*: Highly accessible; Python + BeautifulSoup/Playwright can scrape most public data legally

**App Usage / Digital Metrics:**
- SimilarWeb for web traffic, mobile app rankings (App Annie / data.ai)
- App download velocity, daily active users (DAU/MAU)
- Signals user engagement for platform businesses before earnings
- *Retail accessibility*: SimilarWeb has free tier; App Store ranking data is scrapeable

**Patent Filings:**
- USPTO and WIPO data reveal R&D direction and competitive positioning
- Patent citation networks identify technology leadership
- *Retail accessibility*: Free via Google Patents, USPTO API; requires NLP to process at scale

**Government Contract Awards:**
- USASpending.gov tracks federal contract awards in real-time
- Highly predictive for defense, healthcare, IT government contractors
- *Retail accessibility*: Entirely free, well-structured API

**Supply Chain Mapping:**
- Import/export records (US Customs data, Bills of Lading via Panjiva/ImportGenius)
- Reveals supplier relationships, component sourcing
- Detects supply disruptions before they're disclosed
- *Retail accessibility*: Moderate cost; some free datasets available

**Shipping / Trade Data:**
- Baltic Dry Index for global commodity shipping
- AIS (Automatic Identification System) vessel tracking for oil tankers, shipping containers
- *Retail accessibility*: MarineTraffic has free tier; full data is expensive

**Earnings-Adjacent:**
- SECwatch.io / EDGAR real-time: Track insider trading filings (Form 4) — insiders buying is bullish signal
- Short interest data (FINRA provides bi-monthly free data)
- Options flow (unusual options activity as leading indicator)
- *Retail accessibility*: High — all SEC filings are free, real-time via EDGAR

### 3.3 Practical Framework for Retail Alternative Data

**Tier 1 — Free and accessible:**
- SEC filings (Form 4 insiders, 13F institutional holdings, 8-K events)
- USASpending.gov (government contracts)
- Job postings via scraping
- App Store rankings
- Web traffic (SimilarWeb free tier)
- Short interest (FINRA bimonthly)

**Tier 2 — Low cost:**
- Full Reddit/Twitter/StockTwits sentiment (APIs)
- Google Trends for product interest
- GitHub activity for tech companies (open source project health)
- Patent data (free but requires processing)

**Tier 3 — Expensive (institutional):**
- Credit card transaction data ($50K+/year)
- Satellite imagery
- Mobile geolocation data

**Key challenge:** Most retail-accessible alternative data requires significant data engineering. The edge from free data sources has largely been competed away by institutional players; the real edge at retail scale comes from combining public data creatively with fundamental analysis.

---

## 4. NLP and Sentiment Analysis in Finance

### 4.1 Earnings Call Analysis

Earnings calls are rich NLP targets. Modern approaches go far beyond simple positive/negative sentiment:

**Hedging language detection:**
- Words like "challenging," "uncertain," "headwinds," "we expect" vs. "we committed to" signal management confidence level
- BERT-based models fine-tuned on financial text outperform dictionary-based approaches
- FinBERT (financial domain BERT) is the standard open-source model

**Topic shift detection:**
- If management spends more time on previous quarter's issues vs. forward guidance, it signals defensiveness
- LDA (Latent Dirichlet Allocation) can track topic proportions across quarters

**Q&A section signals:**
- Analyst questions focus on what's concerning; management's word choices in responses are revealing
- Duration of answers to specific questions correlates with issue sensitivity
- Number of analysts dropping off calls (engagement metric)

**Management tone vs. guidance accuracy:**
- Academic research shows management tone in calls predicts earnings revision direction
- Sudden shifts in tone relative to prior quarters are particularly informative

**Practical tools:**
- Seeking Alpha, Motley Fool provide earnings call transcripts; SEC hosts official transcripts (8-K)
- Python + transformers library for inference with FinBERT
- Some quantitative hedge funds have proprietary models; open-source alternatives perform well

---

### 4.2 News Sentiment

**Event-driven vs. background sentiment:**
- **Event-driven**: News about specific catalysts (FDA approval, merger, earnings surprise) — immediate price reaction, largely efficient within hours
- **Background**: Slowly accumulating sentiment about industry trends, regulatory environment — less efficient, broader time horizon

**GDELT Project:**
- Free, massive news sentiment database covering global English news
- Provides event-driven sentiment scores but is noisy and requires cleaning

**Bloomberg/Refinitiv News Analytics:**
- Institutional-grade news sentiment; expensive but well-validated
- Scores relevance, novelty, and sentiment separately

**Practical approach at retail scale:**
- Focus on unique signals: regulatory developments, supply chain news, management changes
- Use free news aggregators + FinBERT inference rather than expensive commercial sentiment
- News sentiment tends to be quickly arbitraged away; combine with slower-moving fundamental signals

---

### 4.3 Social Media Signal Extraction

**StockTwits:**
- Financial-specific microblogging; participants self-identify as bullish/bearish
- Sentiment aggregation has been shown to predict short-term price movements (1-5 days)
- Easy to access via StockTwits API (free with registration)
- Signal decays rapidly; best for identifying unusual sentiment spikes

**Reddit (r/wallstreetbets, r/investing):**
- WSB is primarily retail-driven momentum/options flow; useful as contrary indicator at extremes
- Message volume spikes precede short squeezes (GameStop, AMC pattern)
- Reddit Pushshift API allows historical analysis; Reddit official API for real-time

**Separating signal from noise:**
- Raw sentiment is mostly noise; focus on **rate of change** in sentiment (velocity) rather than level
- Account quality matters: filter by account age, post history to remove bots
- Combine social sentiment with short interest data: high short interest + rising retail sentiment = squeeze setup
- Be cautious of sentiment loops: price rises generate positive sentiment, which drives further price rises, regardless of fundamentals

**LLM-based approaches (2024-2025):**
- Using GPT-4/Claude to summarize and extract nuanced sentiment from financial text outperforms traditional NLP on out-of-sample tests
- Zero-shot classification works surprisingly well for simple financial sentiment tasks
- Fine-tuned models on financial corpora (FinBERT, BloombergGPT) outperform for domain-specific tasks

---

## 5. Machine Learning for Stock Selection

### 5.1 Gradient Boosting (XGBoost, LightGBM)

Gradient boosting is the dominant ML method for tabular cross-sectional data (stock selection), consistently outperforming neural networks on structured financial data:

**How it works:**
- Builds an ensemble of shallow decision trees sequentially, each correcting the errors of the previous
- XGBoost and LightGBM are optimized implementations with regularization to prevent overfitting
- Naturally handles mixed feature types (financial ratios, momentum, alternative data)
- Feature importance output enables interpretability

**Cross-sectional return prediction:**
- Target: next month's return rank (relative to universe) — predict cross-sectional outperformance, not absolute returns
- Features: factor exposures (value, momentum, quality), technical indicators, alternative data signals
- Training: expanding window (train on all data up to period T, predict T+1) or rolling window
- Objective: rank correlation (Spearman IC) between predicted and realized returns, not MSE

**Typical feature set:**
- Valuation ratios: P/E, P/B, EV/EBITDA, P/FCF
- Momentum: 1-month, 3-month, 6-month, 12-1 month returns
- Quality: ROE, ROA, gross margin, debt/equity, interest coverage
- Earnings: EPS revision direction, earnings surprise magnitude
- Technical: RSI, 52-week high proximity, volume trends

---

### 5.2 Avoiding Overfitting in Financial ML

Financial time series is notoriously difficult for ML due to:
- **Low signal-to-noise ratio**: Return predictability R² is typically 0.5-2% — tiny but real
- **Non-stationarity**: Factor relationships shift across regimes
- **Lookahead bias**: Using data not available at prediction time
- **Survivorship bias**: Training only on stocks that survived
- **Small effective sample size**: Monthly returns → 30 years = 360 observations per stock

**Critical practices:**
1. **Walk-forward validation**: Never use future data. Retrain model at each time step and evaluate only on unseen future data
2. **Regime awareness**: Split test sets by economic regime (expansion/recession, high/low volatility)
3. **Feature importance stability**: Features that are important across multiple independent time periods are more trustworthy than those important in specific subperiods
4. **Regularization**: L1/L2 penalties, tree depth limits, minimum samples per leaf
5. **Multiple hypothesis correction**: When testing many features, correct p-values (Bonferroni or FDR). Harvey and colleagues showed most factor discoveries are false positives without this
6. **Out-of-sample testing on new markets**: A US-discovered factor should work in international markets if real

**Common backtesting pitfalls (Lopez de Prado's framework):**
- **Data snooping**: Testing many variations until finding one that works
- **Overfit in-sample**: Model explains historical data but doesn't generalize
- **Transaction costs**: Live trading costs (bid-ask, market impact) erode paper returns significantly for high-turnover strategies
- **Liquidity assumptions**: Small-cap strategies often fail live because of market impact

---

### 5.3 Ensemble Methods

Combining multiple diverse models generally outperforms any single model:
- **Model diversity is key**: Gradient boosting + logistic regression + random forest are more diverse than three gradient boosting models
- **Blending**: Average predictions from multiple models, optionally with learned weights
- **Stacking**: Train a meta-model on out-of-fold predictions of base models
- Factor model combinations in practice: AQR combines value, momentum, quality with equal weight after normalizing each signal's volatility

---

### 5.4 Neural Networks for Time Series

**LSTM / GRU (Recurrent Neural Networks):**
- Designed for sequential data; can theoretically capture regime transitions
- In practice, often underperform simpler methods on financial time series due to limited data
- Require extensive hyperparameter tuning

**Transformers for financial time series:**
- Attention mechanisms capture long-range dependencies in price/fundamental sequences
- Pre-trained models on financial text (BloombergGPT, FinBERT) can be fine-tuned for specific tasks
- Research is active (2023-2025) but results are mixed: benefits often come from the NLP components, not time-series modeling

**Practical recommendation:**
- For stock selection: gradient boosting > neural networks for most practitioners
- For NLP (earnings calls, news): transformer-based models (FinBERT, GPT fine-tuning) clearly win
- Neural networks are most valuable when you have very large, diverse datasets — rare for individual practitioners

---

## 6. Statistical Arbitrage and Pairs Trading

### 6.1 Pairs Trading

The simplest form of statistical arbitrage: identify two stocks that historically move together (high correlation), and trade mean reversion when they diverge.

**Three methodological approaches:**
1. **Distance approach**: Find pairs with minimum sum of squared price differences; trade when spread exceeds k standard deviations. Simple but empirically found to be profitable in studies
2. **Cointegration approach**: Test for long-run equilibrium using Engle-Granger or Johansen tests. Statistically more rigorous — cointegration implies the spread is stationary with a guaranteed convergence tendency
3. **Copula approach**: Models the joint distribution more flexibly, capturing non-linear dependence

**Cointegration in practice:**
- Two price series X and Y are cointegrated if aX + bY = u (where u is stationary)
- Even though X and Y individually have unit roots (random walks), their combination is mean-reverting
- The Engle-Granger test: regress Y on X, test residuals for stationarity (ADF test)
- Johansen test: handles multiple cointegrating relationships

**Pairs trading signals:**
- Enter long/short when spread > 2σ from mean
- Close when spread returns to 0 or crosses
- Stop-loss when spread exceeds 3-4σ (relationship may have broken)

**Pair selection criteria:**
- Same sector/industry (economic justification for co-movement)
- Similar size (reduces regime-specific divergences)
- Stable beta ratio over time

---

### 6.2 Full Statistical Arbitrage

True StatArb (as practiced by D.E. Shaw, Renaissance) extends pairs to portfolios of hundreds of stocks:

**Two-phase portfolio construction:**
1. **Scoring phase**: Each stock receives a signal score (short-term mean reversion, momentum, sector trends)
2. **Risk reduction phase**: Combine stocks into beta-neutral, factor-neutral portfolio using risk models (BARRA, Axioma). The portfolio is long high-score stocks, short low-score stocks, with all systematic factor exposures hedged

**Key challenges:**
- Signal decay: StatArb returns dropped significantly 1998-2007 as competition increased (Khandani & Lo study)
- "Quant quake" of August 2007: Multiple StatArb funds simultaneously liquidated, causing correlated losses as they had similar positions. Showed model crowding risk
- Market microstructure: StatArb relies on large numbers of small-edge trades; transaction costs and market impact compress returns at retail scale

**What retail investors can adapt:**
- Simple pairs trading within sector is implementable (same-sector pairs screen for cointegration)
- Avoid attempting high-frequency or microstructure-based StatArb — institutional edge is unassailable there
- Medium-frequency (monthly rebalancing) factor-based strategies are more accessible

---

### 6.3 Mean Reversion Signals

**Market microstructure mean reversion:**
- Daily/weekly reversal: Stocks that fell most last week tend to rebound slightly (and vice versa)
- This is the short-term reversal premium; negatively correlated with momentum
- Institutional in nature: difficult to exploit due to market impact

**Fundamental mean reversion:**
- EV/EBITDA, P/E ratios mean-revert over 3-5 year cycles
- Earnings revisions mean-revert: over-optimistic upgrades are followed by downgrades
- Operating margins: Industries with high margins attract competition, compress margins toward industry average

---

## 7. Risk-Adjusted Assessment

### 7.1 Sharpe Ratio

The standard risk-adjusted return metric:

```
Sharpe = (Portfolio Return - Risk-free Rate) / Standard Deviation of Returns
```

**Limitations (important):**
- Assumes returns are normally distributed — financial returns have fat tails; extreme losses are more common than normal distribution predicts
- Penalizes both upside and downside volatility equally — rewards strategies that suppress volatility through hidden tail risk (selling options, Ponzi schemes show high Sharpe until failure)
- Can be manipulated through return smoothing or discretionary pricing
- Berkshire Hathaway's Sharpe ratio was ~0.79 (1976-2017), higher than most managed funds; S&P 500 Sharpe was ~0.49 in same period
- Good Sharpe ratios by context: > 1.0 is excellent, 0.5-1.0 is good, < 0.5 is poor

**When to use it:**
- Comparing strategies with similar risk profiles
- Scaling position sizes (higher Sharpe strategies deserve more capital)
- Requires sufficient data: unreliable with < 3 years of monthly returns

---

### 7.2 Sortino Ratio

A modification of Sharpe that penalizes only downside deviation:

```
Sortino = (Portfolio Return - Target Return) / Downside Deviation
```

Where downside deviation measures only returns below the target (MAR — Minimum Acceptable Return).

**Why it's better for asymmetric strategies:**
- A strategy that earns steady 2% monthly with occasional +20% spikes has a "bad" Sharpe (high volatility) but a great Sortino (all volatility is upside)
- More consistent with investor utility: most investors care about losses, not about gains being lumpy
- Standard in hedge fund evaluation alongside Sharpe

---

### 7.3 Maximum Drawdown Analysis

**Maximum drawdown** = peak-to-trough decline before a new peak is reached.

```
MaxDD = (Trough Value - Peak Value) / Peak Value
```

**Why it matters:**
- A 50% drawdown requires a 100% gain to recover
- Behaviorally, most investors cannot tolerate large drawdowns without selling at the bottom
- Strategy viability: a strategy with 80% CAGR but -70% max drawdown is psychologically nearly impossible to maintain

**Calmar Ratio:**
```
Calmar = CAGR / Max Drawdown (absolute value)
```
Popular in hedge fund evaluation; penalizes strategies with large drawdowns.

**Time underwater:** How long a strategy is below its previous high watermark matters as much as the depth of drawdown. Professional fund managers are often fired after 18 months underwater, regardless of strategy quality.

---

### 7.4 Value at Risk (VaR) and Expected Shortfall

**VaR:**
- "With 95% probability, the portfolio will not lose more than X in one day"
- E.g., 5% daily VaR of $1M means on 1 in 20 days, losses will exceed $1M

**Problems with VaR:**
- Tells you nothing about the magnitude of losses beyond the threshold
- Does not satisfy subadditivity: a diversified portfolio can have higher VaR than sum of parts
- Created perverse incentives pre-2008 (banks optimized to VaR limits, concentrating tail risk)

**Expected Shortfall (CVaR — Conditional VaR):**
- Average loss conditional on exceeding VaR threshold
- "When we lose more than 5% in a day, we lose X on average"
- More robust risk measure; now preferred by Basel III banking regulations
- Satisfies coherent risk measure axioms including subadditivity

**Practical use at retail scale:**
- Compute rolling 95% 30-day VaR to monitor position risk
- Monte Carlo simulation more reliable than historical VaR for sparse data
- Expected shortfall is the right metric when tail risk (black swans) dominates

---

### 7.5 Kelly Criterion in Practice

The Kelly criterion maximizes the long-term expected geometric growth rate:

**Binary outcome formula:**
```
f* = p - q/b = p - (1-p)/b
```

Where p = win probability, q = loss probability (1-p), b = ratio of gain to loss.

**Investment generalization:**
```
f* = p/l - q/g
```

Where l = fraction lost on loss, g = fraction gained on win.

**Why full Kelly is rarely used in practice:**
- Full Kelly maximizes long-term growth but can cause catastrophic short-term volatility (100% position in extreme cases)
- Requires perfectly known outcome probabilities — impossible in markets
- Risk-averse investors should use fractional Kelly (quarter Kelly is common) to reduce drawdowns
- Kelly bets are extremely sensitive to probability estimation errors: a slightly wrong p leads to dramatically different position sizing

**Practical implementation:**
- Use as a position sizing **ceiling**, not a precise target
- A "half Kelly" portfolio earns ~75% of full Kelly returns but with ~50% of the variance
- Focus on identifying positive-edge situations first; Kelly tells you only how much to bet given an edge already exists

---

## 8. Key Academic Papers and Resources

### Essential Academic Papers

| Paper | Authors | Key Finding |
|-------|---------|-------------|
| "The Cross-Section of Expected Stock Returns" (1992) | Fama, French | Beta alone fails; size and value matter |
| "Common Risk Factors in Returns on Stocks and Bonds" (1993) | Fama, French | Three-factor model |
| "Returns to Buying Winners and Selling Losers" (1993) | Jegadeesh, Titman | Momentum premium documented |
| "A Five-Factor Asset Pricing Model" (2015) | Fama, French | Adds profitability and investment |
| "Value and Momentum Everywhere" (2013) | Asness, Moskowitz, Pedersen | Both premia across 8 asset classes |
| "Fact, Fiction and Value Investing" (2015) | Israel, Moskowitz, Asness | Value is real, not data mining |
| "... and the Cross-Section of Expected Returns" (2016) | Harvey, Liu, Zhu | Most factors are false positives |
| "The Other Side of Value: Gross Profitability Premium" (2013) | Novy-Marx | Profitability predicts returns |
| "What Happened to the Quants in August 2007?" | Khandani, Lo | Quant crowding risk documented |

### Free Data Resources

| Resource | URL | Contents |
|----------|-----|----------|
| Kenneth French Data Library | mba.tuck.dartmouth.edu/pages/faculty/ken.french | Factor return data (daily/monthly) |
| AQR Data Sets | aqr.com/Insights/Datasets | Factor portfolios, updated regularly |
| WRDS (Wharton Research Data) | wrds-web.wharton.upenn.edu | Academic access; requires affiliation |
| EDGAR / SEC | sec.gov/edgar | All public company filings |
| USASpending.gov | usaspending.gov | Government contract awards |
| FINRA Short Interest | finra.org/investors/tools-calculators/short-interest | Bi-monthly short interest |

### Practical Python Libraries

| Library | Purpose |
|---------|---------|
| `pandas-datareader` | Download factor data from Ken French, FRED, Yahoo |
| `statsmodels` | CAPM, factor regressions, cointegration tests (ADF, Johansen) |
| `xgboost`, `lightgbm` | Cross-sectional ML stock selection |
| `transformers` (HuggingFace) | FinBERT and other financial NLP models |
| `quantstats` | Portfolio performance analytics (Sharpe, Sortino, drawdowns) |
| `pyfolio` | Tearsheet generation, factor exposure analysis |
| `ffn` | Financial functions: drawdown, CAGR, Kelly criterion |

---

## 9. Synthesis: What Actually Works for a Sophisticated Retail Investor

### 9.1 High-Confidence Approaches

**Multi-factor screening:**
- Combine value (EV/EBITDA, P/FCF), momentum (6-12 month return), quality (ROE, low debt), and low investment (low asset growth) into a composite score
- Equal-weight factor exposures or use historical information ratios as weights
- Rebalance quarterly (monthly is rarely worth transaction costs for individuals)
- Universe: focus on mid/large-cap to avoid liquidity issues

**Earnings quality screening:**
- Low accruals (operating earnings > accounting earnings) predicts positive returns
- Revenue recognition acceleration is a red flag (Enron-era classic)
- Free cash flow quality: compare FCF to net income consistently

**Earnings revision momentum:**
- Stocks with improving consensus EPS estimates over 3 months tend to outperform
- Earnings Revision Ratio (ERR): upgrades/(upgrades + downgrades) is a leading indicator

### 9.2 Moderate Confidence

**NLP on earnings calls:**
- Detecting management tone shifts and hedging language is achievable with FinBERT
- Needs to be combined with fundamental signals to reduce noise

**Government contracts / insider buying:**
- Form 4 insider purchases (especially CEO/CFO buying) have a documented 12-month return premium
- USASpending contract awards for government-dependent sectors (defense, healthcare IT)

**Short interest as contrarian indicator at extremes:**
- Stocks with >30% short interest that show improving fundamentals are squeeze candidates
- High short interest + rising fundamentals + positive momentum = powerful setup

### 9.3 Lower Confidence / Caution Required

**Social media sentiment:**
- Useful for identifying unusual activity and momentum inflection points
- Dangerous as standalone signal — crowds are often wrong at extremes
- Best as a secondary filter, not a primary driver

**Pairs trading:**
- Works theoretically but profitability has declined as competition increased
- Sector pairs with strong economic linkages (same commodity input, same customer base) are more robust

**ML-only approaches:**
- Pure ML without economic intuition tends to discover spurious patterns
- Always require interpretable feature importance and out-of-sample validation on new time periods or markets

### 9.4 Risk Management Principles

1. **Position sizing**: Kelly criterion as a ceiling, not a target. Size by inverse volatility for equal-risk contributions
2. **Diversification across factors**: No single factor is reliable every year. Combining 4-6 uncorrelated signals is more robust
3. **Regime awareness**: Track economic cycle signals (credit spreads, PMI, yield curve) to adjust factor weights
4. **Drawdown limits**: Pre-define maximum acceptable drawdown per strategy; if hit, pause and investigate
5. **Transaction costs**: For any systematic strategy, estimate and subtract realistic costs before committing capital

---

*Sources: Fama & French (1992, 1993, 2015), Asness, Moskowitz & Pedersen (2013), Jegadeesh & Titman (1993), Harvey, Liu & Zhu (2016), Bridgewater All Weather Story (2012), AQR Research Library (2024-2025), Wikipedia (Fama-French model, Factor investing, Statistical arbitrage, Cointegration, Sharpe ratio, Sortino ratio, Kelly criterion, Value at Risk, Alternative data)*
