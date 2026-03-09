# Index Methodologies Research

*Research compiled: 2026-03-08*

---

## Overview

This document covers how major equity indices are constructed, maintained, and how factor-based and ESG indices extend those principles. Understanding these methodologies matters for investment research because: (a) index inclusion/exclusion creates price pressures and signals, (b) index construction rules reflect consensus definitions of "investable universe," and (c) factor index definitions operationalize academic theories about what drives returns.

---

## 1. FTSE UK Index Series (FTSE Russell)

### Core Structure

FTSE Russell (owned by London Stock Exchange Group, LSEG) manages the FTSE UK Index Series. The principal indices are:

| Index | Coverage |
|-------|----------|
| FTSE 100 | 100 largest UK-listed companies by free-float market cap |
| FTSE 250 | Next 250 (ranks 101–350) |
| FTSE 350 | FTSE 100 + FTSE 250 combined |
| FTSE All-Share | ~600 companies covering ~98% of eligible UK market cap |
| FTSE SmallCap | Companies below FTSE 350 threshold |

### Eligibility Criteria

For inclusion in FTSE UK Series, a company must:

- Be **listed on the London Stock Exchange Main Market** (not AIM, which has its own index series)
- Be denominated and have the majority of trading in **sterling or euros**
- Pass a **liquidity screening** — turnover by value assessed over 12 months
- Have a **free float of at least 25%** of total shares outstanding (shares available to public investors, excluding strategic/locked holdings)
- Meet nationality rules: the company should be incorporated in, and derive its primary income from, qualifying countries

### Free Float Adjustment

FTSE UK indices use **free-float market capitalisation** rather than full market cap. Strategic holdings (government stakes, founder family stakes, cross-holdings above certain thresholds) are excluded from the float. This adjusts each company's effective weight so that only the investable portion counts.

Bands are used to prevent constant reweighting from minor float changes: floats are rounded to the nearest 5% band.

### Quarterly Reviews

Reviews occur four times per year, typically on the **Wednesday after the first Friday of March, June, September, and December**. Changes take effect at close of the next trading day. Reviews use market cap data from the close of business the night before the review.

**Promotion/relegation rules:**
- A company ranked **90 or higher** by free-float market cap is automatically **promoted** to the FTSE 100
- A company ranked **111 or lower** is automatically **relegated** to the FTSE 250
- The buffer zone (91–110) preserves stability — existing members stay until they fall below rank 110

This means roughly 5–10 changes per year in the FTSE 100, fewer when markets are stable.

### Sector Classification: ICB (Industry Classification Benchmark)

FTSE Russell developed the **Industry Classification Benchmark (ICB)** jointly with Dow Jones. ICB classifies companies into:
- 11 **Industries** (top level, e.g., Technology, Financials)
- 20 **Supersectors**
- 45 **Sectors**
- 173 **Subsectors** (most granular)

Classification is based on the primary source of a company's revenue. ICB is widely used by European indices; MSCI uses its own GICS system for US/global classification.

### Key Characteristics vs S&P 500

- FTSE 100 is **rules-based** — automatic promotion/demotion based on size rank (no committee)
- Heavy concentration in **energy, mining, financials** — less tech-heavy than US indices
- Many "UK-listed" companies generate the majority of revenue globally (e.g., Shell, Rio Tinto, HSBC)
- Created in January 1984 with a base of 1,000

---

## 2. S&P 500

### Core Structure

Managed by **S&P Dow Jones Indices** (subsidiary of S&P Global), the S&P 500:
- Tracks **500 leading US public companies**
- Covers approximately **80% of total US equity market capitalisation**
- Is a **float-adjusted, market-cap-weighted** index
- Actually includes **503 constituents** as three companies have two share classes listed

### Key Distinction: Committee-Based Selection

Unlike FTSE's purely mechanical rules, the S&P 500 uses a **Committee** that applies judgment. This is one of the most important differences:

- The **Index Committee** meets regularly and applies discretion about which stocks qualify
- A company can meet all quantitative criteria but still be excluded if the committee believes it isn't representative
- The committee considers **sector representation** — ensuring the index reflects the US economy's composition
- This means timing of additions/removals can be delayed, accelerated, or blocked on qualitative grounds

### Eligibility Criteria (as of 2024)

| Criterion | Requirement |
|-----------|------------|
| Domicile | US company (incorporated in US) |
| Exchange listing | NYSE, NYSE Arca, NYSE American, Nasdaq, CBOE BZX |
| Market cap | Minimum $18 billion (unadjusted) |
| Annual dollar value traded | At least 1.0x the company's float-adjusted market cap over preceding 12 months |
| Public float | At least 50% of outstanding shares |
| Profitability | Positive reported earnings in the most recent quarter AND positive as-reported earnings sum over the most recent four consecutive quarters |
| IPO seasoning | Must have traded for at least 12 months |
| Share class | Common stock (no limited partnerships, master limited partnerships, etc.) |

### The Profitability Requirement

The positive earnings rule is notable — it means **unprofitable companies cannot join the S&P 500** even if their market cap qualifies. This was a factor in Tesla's delayed inclusion (Tesla had to demonstrate consistent profitability). This rule differs from purely mechanical indices that use only market cap.

S&P uses **GAAP as-reported earnings** — not adjusted/pro forma earnings favoured by management and analysts.

### Float Adjustment Methodology

S&P calculates **Investable Weight Factors (IWFs)** to determine the float. Excluded from float:
- Holdings by government entities
- Holdings by corporate officers and directors
- Holdings > 5% by any single entity not subject to SEC rules on insider reporting
- Strategic cross-holdings

### Index Maintenance and Rebalancing

- Changes are announced **several days before** implementation
- **No fixed rebalancing schedule** — changes happen as needed (acquisitions, delistings, bankruptcies, etc.)
- **Reconstitution** is ongoing rather than periodic; the committee can act between quarterly meetings

### S&P Quality Rankings (Legacy System)

S&P historically published **Quality Rankings** (A+, A, A-, B+, B, B-, C, D) based on 10-year records of earnings and dividend stability and growth. These are distinct from the S&P 500 index membership:
- A+ = highest quality (most stable, consistent earnings and dividend growth)
- Used by income investors as a quality signal
- Now somewhat superseded by newer factor indices and ESG scores, but still referenced

---

## 3. MSCI Methodology

### Company Background

MSCI (Morgan Stanley Capital International) is an independent index and research company (spun off from Morgan Stanley in 2009, NYSE: MSCI). As of December 2024, approximately **$16.9 trillion** in assets under management are benchmarked to MSCI indices. MSCI offers over 246,000 indices globally.

### Market Classification Framework

MSCI categorises markets into three tiers based on **economic development, market accessibility, and infrastructure**:

| Classification | Countries (approx.) | Examples |
|----------------|---------------------|---------|
| Developed Markets (DM) | 23 | US, UK, Japan, Germany, Australia |
| Emerging Markets (EM) | 24 | China, India, Brazil, Korea, Taiwan |
| Frontier Markets (FM) | 28 | Vietnam, Morocco, Romania, Bahrain |
| Standalone Markets | — | Markets not meeting criteria for any tier |

### Criteria for Market Classification

MSCI evaluates markets on three pillars:

1. **Economic development** — GNI per capita vs. World Bank thresholds
2. **Size and liquidity** — Number of qualifying securities, company size, liquidity
3. **Market accessibility** — Openness to foreign investment, capital controls, currency convertibility, clearing/settlement infrastructure, regulatory environment, investor protection

Markets are reviewed annually in the **MSCI Annual Market Classification Review**, published in June. There is a "watchlist" and observation period before reclassification (typically 1–3 years), providing predictability.

### Index Construction: Size Segmentation

Within each market, MSCI applies a consistent size framework:

| Segment | Target Coverage of Market Cap |
|---------|-------------------------------|
| Large Cap | ~70% |
| Mid Cap | ~85% cumulative (adds ~15%) |
| Small Cap | ~99% cumulative |
| Micro Cap | Remainder |

The combined **MSCI Standard** covers the top 85% (Large + Mid). MSCI **All Cap** covers top 99%.

### Key Indices

| Index | Coverage |
|-------|---------|
| MSCI ACWI (All Country World Index) | 23 DM + 24 EM, ~2,500 stocks, ~85% of each market |
| MSCI World | 23 developed markets only |
| MSCI EAFE | Europe, Australasia, Far East (21 DM ex-US/Canada) |
| MSCI Emerging Markets | 24 emerging market countries |
| MSCI Frontier Markets | 28 frontier markets |

### Free Float Adjustment

Like FTSE, MSCI uses **free float-adjusted market capitalisation**. Float bands of 5% increments are applied. MSCI requires a minimum free float of 15% for inclusion.

### Rebalancing

- **Quarterly reviews** in February, May, August, November
- **Semi-annual full rebalancing** in May and November (when size changes, market reclassifications, and Global Investable Market Indices updates occur)
- Changes announced approximately **2 weeks before** implementation

### Handling Dual-Listed Companies

MSCI generally includes a company in only **one market** (where it has its primary listing), avoiding double-counting. Where a company is listed in multiple markets, MSCI applies a "home market" determination based on where the majority of trading occurs and where headquarters are located.

---

## 4. Russell Reconstitution

### Overview

Russell Indices (now owned by FTSE Russell) are maintained through an **annual reconstitution process** — a fundamental difference from S&P's ongoing committee-based system.

### Key Russell Indices

| Index | Coverage |
|-------|---------|
| Russell 3000 | 3,000 largest US stocks by market cap (~98% of US equity market) |
| Russell 1000 | Top 1,000 (large cap) |
| Russell 2000 | Bottom 2,000 (small cap) — widely watched small-cap benchmark |
| Russell Midcap | Smallest 800 stocks of Russell 1000 |
| Russell Microcap | 4,000 small/micro cap |

### The Annual Reconstitution Process

Unlike S&P 500 which makes changes throughout the year via committee, Russell reconstitutes **once a year**:

1. **Ranking date**: End of May — all eligible US equities are ranked by total market cap
2. **Preliminary membership list**: Published in early June (tentative additions/deletions)
3. **Final membership list**: Published mid-June
4. **Reconstitution date**: Last Friday of June — new index goes live at market close

### Eligibility Rules

- Must be **US company** listed on eligible exchanges
- Market cap above minimum threshold (breakpoints shift each year with market conditions)
- Minimum price of **$1.00** per share
- Minimum total market cap (adjusted each year; approximately $30 million as of recent years)
- Percentage of shares available to public must pass float screening

### Market Cap Breakpoints

Unlike FTSE's fixed number (100, 250), Russell uses **floating breakpoints** that change every year based on where the actual US market cap distributions fall. This means:
- The cutoff between Russell 1000 and Russell 2000 is not a fixed dollar amount — it moves with the market
- Stocks can cross boundaries as markets shift, creating significant annual "reconstitution events"

### Reconstitution Effect

The annual reconstitution creates a well-documented **trading effect**:
- Passive funds tracking Russell indices must buy additions and sell deletions
- Hedge funds anticipate additions/deletions and trade ahead
- Price pressure can be significant, especially for smaller Russell 2000 additions
- Academic research has documented consistent abnormal returns around reconstitution dates

### Key Difference vs S&P: Rules vs Committee

| Feature | Russell | S&P 500 |
|---------|---------|---------|
| Selection method | Purely mechanical formula | Committee with discretion |
| Timing | Annual (June) | Ongoing as needed |
| Style indices | Same stock can appear in both growth and value | No overlap in style sub-indices |
| Buffer zones | Minimal (float adjustment only) | Promotion/demotion buffers |

---

## 5. Factor Indices and Smart Beta

### Background: From CAPM to Multi-Factor Models

The original Capital Asset Pricing Model (CAPM, 1960s) proposed that only one factor — **market beta** — explained expected returns. Academic research challenged this:

- **Fama-French 3-Factor Model (1992)**: Added **size** (small minus big, SMB) and **value** (high minus low book-to-market, HML) to market beta
- **Carhart 4-Factor Model (1997)**: Added **momentum**
- **Fama-French 5-Factor Model (2015)**: Added **profitability** and **investment** factors

These academic findings created the intellectual foundation for **factor investing** and **smart beta**.

### What Is Smart Beta?

Smart beta strategies:
- Passively track an index (like traditional index funds)
- But that index is constructed using **alternative weighting schemes** — not pure market cap
- Target specific **factors** believed to generate excess risk-adjusted returns
- As of 2024, smart beta ETFs manage approximately **$1.56 trillion** in global assets

### Major MSCI Factor Indices

MSCI offers dedicated **Factor Indices** for six core factors:

#### 1. Quality Factor
**Definition**: High return on equity (ROE) + stable earnings growth + low financial leverage

Specific metrics used by MSCI:
- **Return on Equity (ROE)**: Net income / book equity
- **Earnings Variability**: Variation in year-over-year EPS and cash earnings over past 5 years
- **Debt-to-Equity**: Total debt / book equity

Stocks are scored on these three variables, z-scored within sectors, and combined into a composite Quality score.

**Why it works**: Quality firms have competitive moats, efficient capital allocation, and lower earnings disappointment risk.

#### 2. Momentum Factor
**Definition**: Price performance over the past 12 months, excluding the most recent month

Specific measurement:
- **Risk-adjusted price momentum**: 12-month trailing return (t-12 to t-1) divided by annualised return volatility
- Most recent month excluded to avoid short-term reversal effects

**Why it works**: Trend persistence — winning stocks continue to outperform for 3–12 months (documented in Jegadeesh & Titman, 1993). However, momentum can crash violently during market reversals.

#### 3. Value Factor
**Definition**: Stocks priced cheaply relative to fundamental value

MSCI Value metrics:
- **Price-to-Book (P/B)**: Market cap / book value of equity
- **Forward Price-to-Earnings (P/E)**: Price / consensus forward earnings
- **Enterprise Value-to-Operating Cash Flow (EV/CFO)**: Enterprise value / operating cash flow

Stocks scoring low on these multiples (i.e., "cheap") score high on the Value factor.

#### 4. Low Volatility Factor
**Definition**: Stocks with lower price volatility

Measurement:
- Standard deviation of weekly local total returns over the trailing 2 years

**Counter-intuitive finding**: Low-volatility stocks tend to deliver better risk-adjusted returns than high-volatility stocks — the "low-volatility anomaly." Possible explanations include investor preference for lottery-like payoffs, leverage constraints among institutional investors.

#### 5. Size Factor
**Definition**: Smaller companies within investable universe

Measurement: Log of full market capitalisation (natural log)

Small caps tend to outperform large caps over long periods (the "size premium"), though this premium has weakened since the 1980s.

#### 6. Dividend Yield Factor
**Definition**: High dividend-paying stocks

Measurement: Trailing 12-month cash dividends per share / price per share

Often used as a proxy for income generation and value.

### How Factor ETFs Are Constructed

1. Start with a parent index (e.g., MSCI World)
2. Score each stock on the factor(s)
3. Tilt or reweight the index toward high-scoring stocks
4. Apply **diversification constraints** (max stock weight, max sector deviation from parent)
5. Rebalance periodically (quarterly or semi-annually) to maintain factor exposure

Many modern factor ETFs are **multi-factor**, combining Quality + Value + Momentum + Low Volatility to diversify factor timing risk.

### Factor Timing and Rotation

Factors are **cyclical** — they don't all outperform simultaneously:

| Factor | Tends to outperform when | Tends to underperform when |
|--------|--------------------------|---------------------------|
| Value | Economic recovery, rising rates | Growth/tech bull markets |
| Quality | Late cycle, risk-off | Early recovery, risk-on |
| Momentum | Trending markets | Sharp reversals |
| Low Volatility | Risk-off, bear markets | Strong bull markets |
| Size (small cap) | Economic expansion | Risk-off, credit stress |

Academic debate continues on whether factor premia are due to **risk** (higher expected return compensates for higher risk) or **mispricing** (behavioral biases create exploitable inefficiencies). The academic consensus suggests both play a role.

---

## 6. ESG Scoring Methodologies

### Overview

ESG scoring has grown dramatically: by Q4 2024, sustainable fund AUM reached $3.2 trillion globally (Morningstar). Three dominant rating providers:

### 6.1 MSCI ESG Ratings

**Coverage**: 17,000+ companies globally (as of 2024)

**Scale**: AAA to CCC (7 tiers)
- AAA, AA = "Leader"
- A, BBB, BB = "Average"
- B, CCC = "Laggard"

**Methodology**:
1. Identify **key ESG issues** for each industry (e.g., carbon emissions critical for energy; labour practices critical for retail)
2. Score each company on relevant issues on a 0–10 scale
3. Weight issues by **exposure** (industry-specific risk exposure) and **management quality** (how well the company manages that risk)
4. Combine into industry-relative rating
5. Also screen for controversial activities (weapons, tobacco, gambling)

**Data sources**: Company filings (10-K, sustainability reports, proxy statements), third-party media, NGOs, regulatory filings, academic sources — approximately 50% from corporate sources, 50% from third-party sources.

**Key critique**: Ratings across ESG providers show low correlation (~0.3–0.5), suggesting significant methodology differences and subjectivity. MSCI's ratings are industry-relative, meaning an oil company can get a high rating if it manages ESG risks better than other oil companies — which may not align with an investor's absolute ESG goals.

### 6.2 Sustainalytics ESG Risk Ratings (Morningstar)

Sustainalytics (acquired by Morningstar in 2020) uses a different approach:

- Measures **unmanaged ESG risk** on an absolute scale (not industry-relative)
- Score ranges from 0–100+ (lower is better, unlike MSCI)
- Categories: Negligible (0-10), Low (10-20), Medium (20-30), High (30-40), Severe (40+)
- Focuses on **financially material** ESG issues
- Widely used as an alternative to MSCI, especially in fixed income ESG

Key distinction from MSCI: Sustainalytics uses an **absolute** risk measure; a utility company cannot offset its carbon risk by being "better than peers" in governance.

### 6.3 S&P Global ESG Scores (via Corporate Sustainability Assessment)

S&P Global conducts an annual **Corporate Sustainability Assessment (CSA)**:
- Annual questionnaire sent to companies (voluntary, self-reported)
- 80–100 questions covering Environment, Social, Governance dimensions
- Used to construct the **Dow Jones Sustainability Indices (DJSI)**
- Companies in top 10–20% of industry join the DJSI

Key difference: S&P CSA is **self-reported data** (companies submit their own answers), while MSCI and Sustainalytics rely more heavily on third-party data. This creates selection bias — companies that complete the questionnaire tend to score higher.

### 6.4 Controversy Scores

Most ESG providers also maintain **controversy scores** that can override or significantly impact overall ratings:
- News-based monitoring for ESG controversies (environmental violations, labour disputes, bribery, product recalls)
- A single major controversy (e.g., oil spill, large-scale fraud) can rapidly lower a company's ESG rating
- MSCI's controversy monitoring is continuous — ratings can be updated between scheduled reviews

### ESG Integration into Mainstream Assessment

ESG is increasingly integrated with financial analysis:
- **Materiality frameworks** (e.g., SASB standards) identify which ESG issues are financially material by industry
- **Climate risk**: Both physical risk (climate events affecting operations) and transition risk (regulatory/market shifts to low-carbon economy) are now assessed
- **MSCI Implied Temperature Rise (ITR)**: Forward-looking metric showing a company's implied warming contribution, expressed in degrees Celsius
- Major index providers now offer ESG variants of mainstream indices (MSCI World ESG Leaders, FTSE4Good, S&P ESG Index)

---

## 7. What Makes Stocks "Quality"

"Quality" is one of the most widely used but inconsistently defined concepts in equity assessment. Here are the major frameworks:

### 7.1 MSCI Quality Factor Definition

Three equally-weighted variables:
1. **High ROE** — profitability relative to book equity
2. **Low earnings variability** — earnings stability over 5 years
3. **Low leverage** — debt-to-equity ratio

Scores are z-scored within each GICS sector (not globally), so quality is assessed relative to sector peers.

### 7.2 S&P Quality Rankings (A+ through D)

Based on **10 years** of earnings and dividend history:
- **Earnings per share growth** — trend and consistency
- **Dividend per share growth** — trend and consistency
- Penalises cyclical variability, interruptions, or declines
- A+ indicates the most stable, consistent, long-term record

This is an older system (predating modern factor indices) that rewards **long-term stability over raw profitability**.

### 7.3 Piotroski F-Score (2000)

Developed by Joseph Piotroski, University of Chicago. Published as "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers" (Journal of Accounting Research, 2000).

**Purpose**: Originally designed to identify which low price-to-book stocks were genuinely cheap vs. financially distressed

**9 binary criteria, each scores 0 or 1** (maximum score = 9):

**Profitability (4 points)**:
1. Positive net income
2. Positive Return on Assets (ROA)
3. Positive operating cash flow
4. Cash flow from operations > net income (earnings quality / accrual quality)

**Leverage, Liquidity, Source of Funds (3 points)**:
5. Long-term debt decreased year-over-year
6. Current ratio improved year-over-year
7. No new shares issued in past year (no dilution)

**Operating Efficiency (2 points)**:
8. Gross margin improved year-over-year
9. Asset turnover improved year-over-year

**Interpretation**:
- Score 8–9: Strong quality — good value opportunity
- Score 5–7: Average
- Score 0–2: Weak — likely a value trap

Piotroski's original paper showed a 23% annual return from 1976–1996 from buying high-F-score stocks and shorting low-F-score stocks.

**Use**: Particularly valuable as a **quality overlay on value screens** — helps avoid "value traps" where cheap stocks are cheap because they're deteriorating businesses.

### 7.4 Altman Z-Score (1968, updated 2012)

Created by NYU Professor Edward Altman. Measures **probability of bankruptcy** using 5 financial ratios.

**Formula**: Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E

Where:
- A = Working Capital / Total Assets (liquidity)
- B = Retained Earnings / Total Assets (cumulative profitability / reinvestment)
- C = EBIT / Total Assets (operating efficiency / asset productivity)
- D = Market Value of Equity / Total Liabilities (solvency)
- E = Sales / Total Assets (asset utilisation efficiency)

**Interpretation**:
- Z > 3.0: Safe zone (low bankruptcy risk)
- 1.8 < Z < 3.0: Grey zone
- Z < 1.8: Distress zone (high bankruptcy risk)

Note: Altman himself noted in a 2019 lecture that more recent data suggests 0 (not 1.8) is the critical threshold.

The Z-Score Plus (2012 update) extends the model to private companies, non-manufacturing companies, and non-US companies.

**Use**: Credit risk assessment, distress screening, portfolio risk management. High Z-scores are a positive quality signal; low Z-scores are a warning sign.

### 7.5 Beneish M-Score (1999)

Created by Professor M. Daniel Beneish, Indiana University. Measures **earnings manipulation probability** using 8 financial ratios.

**8 Variables**:
1. **DSRI** (Days' Sales in Receivables Index) — rising receivables relative to sales can indicate channel stuffing
2. **GMI** (Gross Margin Index) — deteriorating margins may pressure managers to inflate earnings
3. **AQI** (Asset Quality Index) — increase in non-current, non-physical assets indicates capitalising expenses
4. **SGI** (Sales Growth Index) — high sales growth companies are incentivised to maintain perception
5. **DEPI** (Depreciation Index) — slowing depreciation rates can indicate over-capitalisation
6. **SGAI** (Sales, General & Administrative Expenses Index) — rising SGA/sales may signal efficiency problems
7. **LVGI** (Leverage Index) — increasing leverage motivates manipulation to meet debt covenants
8. **TATA** (Total Accruals to Total Assets) — high accruals relative to cash earnings is a classic manipulation signal

**Interpretation**:
- M-Score < -1.78: Unlikely manipulator
- M-Score > -1.78: Likely manipulator

Famous application: Cornell students used the M-Score in 1998 to predict Enron was manipulating earnings — when the stock was at $48, three years before collapse.

**Use**: Forensic accounting overlay on quality assessment. Helps identify companies where "quality" financial metrics may be manufactured. High-quality investment implies M-Score should be strongly negative (well below -1.78).

### 7.6 Composite Quality Assessment in Practice

Professional investors typically combine multiple lenses:

| Signal | What It Detects |
|--------|----------------|
| High ROE + stable earnings (MSCI Quality) | Competitive advantage, capital efficiency |
| Strong Piotroski F-Score | Financial health trajectory |
| High Altman Z-Score | Distance from distress |
| M-Score well below -1.78 | Earnings are real, not manipulated |
| Low earnings variability | Resilience across economic cycles |
| FCF/NI ratio near 1.0 | Cash conversion quality (earnings are cash-backed) |
| Conservative accounting (low accruals) | Earnings quality |

**True quality** stocks typically score well across all these dimensions simultaneously: profitable, improving, not levering up, generating real cash, not manipulating numbers.

---

## 8. Implications for Investment Research Platforms

### What These Methodologies Signal

1. **Index inclusion** is a formal endorsement of investability — minimum size, liquidity, profitability
2. **Factor scores** (Quality, Momentum, Value, Low Vol) translate academic research into tradeable signals
3. **ESG ratings** assess non-financial risks increasingly seen as financially material
4. **Quality scores** (Piotroski, Altman, MSCI Quality) help distinguish truly excellent businesses from superficially cheap ones

### Key Tensions

- **Rules vs. Discretion**: FTSE/Russell are mechanical; S&P uses committee judgment. Mechanical is more predictable but may include poor-quality companies. Committee can apply judgment but creates inconsistency and potential bias.
- **Relative vs. Absolute ESG**: MSCI ESG is industry-relative (oil company can score well vs. other oil companies); Sustainalytics is absolute. Neither is "right" — depends on investor objective.
- **Factor timing**: No single factor always outperforms. Multi-factor approaches diversify this but reduce pure-factor exposure.
- **Quality definitions vary**: MSCI Quality = ROE + stability + low leverage; Piotroski = 9-point financial health checklist; Altman = bankruptcy distance. They capture overlapping but distinct aspects.

### Data Points That Drive Index Membership

For practical research platforms, the key inputs that determine index membership and factor scores:

| Data Point | Why It Matters |
|------------|---------------|
| Free-float market cap | FTSE/MSCI inclusion threshold |
| Shares outstanding + holder breakdown | Float calculation |
| GAAP earnings (trailing 4 quarters) | S&P 500 profitability requirement |
| Return on Equity | MSCI Quality, general quality assessment |
| Earnings per share (5-year trend) | S&P Quality Rankings, earnings stability |
| Debt-to-equity | MSCI Quality, Piotroski, Altman |
| Operating cash flow vs net income | Piotroski F4, accrual quality |
| 12-month price return | MSCI Momentum factor |
| Price volatility (52-week) | MSCI Low Volatility factor |
| Price-to-Book, Forward P/E | MSCI Value factor |
| Working capital, retained earnings | Altman Z-Score |
| Receivables, gross margins, accruals | Beneish M-Score |
| Carbon emissions, safety incidents | ESG environmental/social inputs |

---

## Sources Consulted

- Investopedia: S&P 500, FTSE, MSCI, smart beta, factor investing, Piotroski F-Score, Altman Z-Score, Beneish M-Score, ESG criteria, MSCI ESG Ratings, momentum investing
- FTSE Russell: UK Capital Market Reforms FAQs, FTSE 100 factsheets
- S&P Global: S&P US Indices Methodology (via Investopedia references)
- MSCI: ESG Ratings Methodology documentation (via Investopedia references)
- Academic: Piotroski (2000), Fama-French (1992, 1996), Altman (1968, 2012), Beneish (1999)
