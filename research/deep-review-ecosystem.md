# Deep Review: Plugin, MCP, and Tooling Ecosystem for Investmentology

**Date**: 2026-03-08
**Reviewer**: tools-researcher (Claude Sonnet 4.6)
**Scope**: Plugins, MCP servers, external tools, data APIs, analytics libraries, competitors

---

## Executive Summary

The MCP ecosystem for finance is nascent but growing rapidly. The most actionable opportunities are: (1) **MaverickMCP** as a drop-in finance MCP with 39+ tools, (2) **OctagonAI MCP** for private market data and earnings transcripts, (3) **OpenBB** as a Python platform with 200+ data connectors, (4) **edgartools** to significantly enhance SEC filing analysis, and (5) **PyPortfolioOpt / Riskfolio-Lib** for portfolio optimization math. The current dependency stack (yfinance + Alpaca + EDGAR + Finnhub + FRED) covers fundamentals but leaves gaps in technical analysis, alternative data, risk analytics, and backtesting. No ready-made brokerage MCP exists yet.

---

## 1. Financial Data MCPs

### What Exists (MCP Ecosystem Survey)

The `appcypher/awesome-mcp-servers` Finance section lists only a handful of relevant entries for stock/equity analysis:

| MCP Server | Source | Stars | Notes |
|------------|--------|-------|-------|
| **Octagon** (official) | `OctagonAI/octagon-mcp-server` | 103 | Free. Public filings, earnings transcripts, financial metrics, stock market data, private market transactions. Listed as official in awesome-mcp-servers. |
| **LongPort OpenAPI** (official) | Not on GitHub publicly | — | Real-time stock market data + AI analysis + trading capabilities. Asia-focused broker. |
| **MaverickMCP** | `wshobson/maverick-mcp` | 405 | Personal-grade, NOT SaaS. 39+ tools: technical indicators, stock screening, portfolio optimization, VectorBT backtesting. Uses Tiingo API. |
| **Yahoo Finance MCP** | `Alex2Yang97/yahoo-finance-mcp` | 234 | Python, comprehensive: historical prices, company info, financial statements, options, news. Direct yfinance wrapper. |
| **yfnhanced-mcp** | `kanishka-namdeo/yfnhanced-mcp` | 5 | TypeScript, production-ready: real-time quotes, earnings, analyst recs, options chains, caching + rate limiting + circuit breaker. |
| **AgentX Yahoo Finance** | `AgentX-ai/yahoo-finance-server` | 37 | Another yfinance MCP. |

**Assessment for Investmentology**: The most immediately valuable is **OctagonAI MCP** (earnings transcripts, private market data, SEC filings) since the current system uses raw EDGAR. MaverickMCP is not directly deployable as-is (local server, requires Tiingo key, TA-Lib install) but its **source code is excellent reference** for what tools to build.

### Bloomberg, Polygon.io, Alpha Vantage, FMP, etc.

**No ready-made MCP servers exist** for these premium data sources as of March 2026. Polygon.io and others offer official Python SDKs but no MCP wrapper.

| Data Source | Official Python SDK | MCP? | Cost |
|------------|---------------------|------|------|
| **Polygon.io** | `polygon-api-client` | No | $29/mo starter |
| **Alpha Vantage** | `alpha_vantage` (4,744 stars) | No | Free tier, 500 req/day |
| **Financial Modeling Prep** | `fmpcloud` | No | Free tier limited |
| **Tiingo** | Via `pandas-datareader` | No | Free tier + paid |
| **IEX Cloud** | `pyEX` | No | Paid, $9/mo starter |
| **Nasdaq Data Link** (Quandl) | `quandl` | No | Free for most |
| **OpenBB** | Yes (62,709 stars, `OpenBB-finance/OpenBB`) | No built-in MCP, but has API | Open source, connects 200+ sources |

**Recommendation**: For raw data, the current yfinance + EDGAR combination is reasonable. The most impactful upgrade would be adding **Tiingo** (already used by MaverickMCP) for more reliable OHLCV data alongside yfinance as fallback. **OpenBB** is the most powerful open-source platform but requires significant integration work.

---

## 2. Brokerage MCPs

**No brokerage MCPs exist** as of March 2026. This is a significant gap in the ecosystem.

| Broker | SDK | MCP? | Notes |
|--------|-----|------|-------|
| **Alpaca** | `alpaca-py` (1,168 stars, official) | No | Already in Investmentology stack |
| **Interactive Brokers** | `ib_async` (1,402 stars, formerly ib_insync) | No | Complex TWS API, async-capable |
| **Schwab** | Official REST API available | No | Acquired TD Ameritrade, unified API |
| **Robinhood** | No official Python SDK | No | Unofficial only, TOS risks |
| **Trading212** / **eToro** | Limited REST APIs | No | UK/EU focused |

**Notable**: OpenAI recently integrated Alpaca's market data functionality as part of ChatGPT for Financial Services (March 2026), signaling brokerage MCPs are coming but not yet public.

**Assessment**: Alpaca is already in the stack for paper trading. The main gap is that the system has no tool to query live Alpaca position state via MCP. This would be a **high-value custom MCP to build** (or a direct Python module in the pipeline).

---

## 3. Claude Plugins (awesome-claude-code-plugins Review)

The `ccplugins/awesome-claude-code-plugins` list has **no financial analysis or investment-specific plugins**. The categories are: Workflow Orchestration, Automation DevOps, Business Sales, Code Quality Testing, Data Analytics, Design UX, Development Engineering, Documentation, Git Workflow, Marketing Growth, Project & Product Management, Security/Compliance/Legal.

Notable existing plugins relevant to Investmentology development (not investment analysis):
- **finance-tracker** (Business Sales category) — tracks financial metrics, not investment research
- **data-scientist** (Data Analytics) — general data science
- **experiment-tracker** — could track model predictions
- **trend-researcher** — generic research agent

**Assessment**: No investment-specific Claude plugins exist. The **finance-tracker** plugin is about business finance, not investment analysis. This represents an opportunity to **publish Investmentology-specific slash commands** as plugins (e.g., `/analyze-ticker`, `/screen-quant-gate`, `/run-pipeline`).

---

## 4. SEC EDGAR Tools

### Current State
The stack uses `sec-api.io` for 13F holdings and Form 4 insider tracking. EDGAR is free-tier.

### Better Tools Available

| Tool | Stars | Description | Integration Effort |
|------|-------|-------------|-------------------|
| **edgartools** (`dgunning/edgartools`) | 1,802 | Full Python library: 10-K, 10-Q, 8-K, XBRL financial statements, full-text search, company lookup | Low — pip install |
| **sec-api-python** (`janlukasschroeder/sec-api-python`) | 286 | 18M+ filings, all 150 types, XBRL-to-JSON, real-time stream, already in stack | Already in use |

**edgartools Assessment**: This is a significant upgrade opportunity. Current EDGAR usage likely relies on raw HTTP calls to the EDGAR API. `edgartools` provides:
- Parsed XBRL financial statements (balance sheet, income statement, cash flow) as DataFrames
- 10-K/10-Q/8-K structured data extraction
- Full-text search across all filings
- Company object model with history

**Recommendation**: Replace raw EDGAR calls with `edgartools`. This would dramatically improve the quality of fundamental data extracted in Layers 1 and 2 — currently, yfinance is the primary fundamentals source and it's flaky. edgartools + SEC direct would be more reliable.

---

## 5. Alternative Data Sources

### What's Available (Non-premium, API-accessible)

| Data Type | Source | Access | Cost |
|-----------|--------|--------|------|
| **Job postings** | Indeed/LinkedIn scraping (ToS issues), BLS API | Indirect | Free (BLS) |
| **Patent filings** | USPTO Patent Center API | REST API | Free |
| **Government contracts** | USASpending.gov API | REST API | Free |
| **App store rankings** | AppFollow API, Sensor Tower (paid) | API | Paid |
| **Web traffic** | SimilarWeb API (paid), CommonCrawl | API | $199/mo+ |
| **Satellite imagery** | NASA Earthdata, Sentinel Hub (EU) | API | Free/cheap |
| **Social sentiment** | Reddit API, Twitter/X API v2 | API | Limited free |
| **Congressional trades** | Quiver Quantitative API | REST | Free tier |
| **Insider transactions** | OpenInsider (scrape), SEC Form 4 via EDGAR | Web/EDGAR | Free |
| **Short interest** | FINRA, SEC Rule 201 data | REST | Free |

**Most Actionable Alternative Data**:
1. **Congressional trading disclosures** (Quiver Quantitative) — free API, known alpha signal
2. **SEC Form 4 insider transactions** — via edgartools, already partially in stack
3. **USPTO patent filings** — free API, useful for R&D-heavy sectors
4. **FINRA short interest** — free, useful for sentiment/squeeze analysis

**Assessment**: The current system has zero alternative data integration. Congressional trading and insider transactions are the highest signal-to-effort opportunities with no cost.

---

## 6. NLP / Sentiment Tools

### FinBERT and Financial NLP

| Tool | Type | Stars | Notes |
|------|------|-------|-------|
| **ProsusAI/finbert** | Pretrained BERT model | ~1,500 (HuggingFace) | Financial sentiment classification (positive/negative/neutral) |
| **FinBERT-Tone** | Fine-tuned variant | Available on HuggingFace | Trained on financial analyst tone |
| **finvader** | VADER for finance | PyPI | Lexicon-based, no model download needed |
| **sec-sentiment** | SEC 10-K sentiment | Available | Pre-built for EDGAR text |

**MCP for Sentiment**: None exist. All are Python libraries requiring local inference or HuggingFace API.

### Earnings Call Transcripts

Current gap: No earnings call transcript analysis in the pipeline. Available options:
- **OctagonAI MCP** — includes earnings transcripts (already in #1 above)
- **Whisper** — transcribe earnings call audio (requires audio source)
- **Seeking Alpha** — earnings transcripts API (paid, $40/mo)
- **Motley Fool / TIKR** — manual extraction only

**Assessment**: Adding FinBERT for news/headline sentiment scoring would be a low-cost enhancement. Run as a lightweight Python function (not requiring GPU for small batches). Primary value: objective sentiment signal vs. agent subjective reading of news. The Simons agent is already meant to be quant-focused but likely doesn't use systematic NLP on news text.

**OctagonAI MCP + earnings transcripts** is the fastest path to improving the news/catalyst analysis layer.

---

## 7. Portfolio Analytics Libraries

| Library | Stars | Capabilities | Integration Effort |
|---------|-------|-------------|-------------------|
| **PyPortfolioOpt** (`PyPortfolio/PyPortfolioOpt`) | 5,530 | Efficient frontier, Black-Litterman, Hierarchical Risk Parity, CVaR optimization | Low — pip install |
| **Riskfolio-Lib** (`dcajasn/Riskfolio-Lib`) | 3,804 | 20+ portfolio optimization methods, factor models, risk decomposition, Monte Carlo | Medium — more complex |
| **QuantLib-Python** | — | VaR, CVaR, fixed income analytics, derivatives | High — complex C++ bindings |
| **empyrical** | ~1,200 | Risk-adjusted returns: Sharpe, Sortino, Calmar, max drawdown | Low — pip install |
| **pyfolio** | ~5,000 | Full portfolio tear sheets, factor attribution | Low — pip install |

### Current Gap
Layer 5 (Timing & Sizing) uses Kelly Criterion but appears to be manual/heuristic sizing. There is no systematic portfolio-level risk analytics.

**Highest Value Additions**:
1. **empyrical** — Add to Layer 6 (Learning) for calibration. Compute Sharpe, Sortino, drawdown on paper portfolio.
2. **PyPortfolioOpt** — Add to Layer 5 for position sizing. Black-Litterman model aligns with multi-agent belief aggregation: agent verdicts → views → B-L portfolio weights.
3. **pyfolio** — Add to reporting/dashboard for full tear sheets.

**Black-Litterman + Multi-Agent Synergy**: This is architecturally elegant. The 6 primary agent confidence scores (Warren 0.18, Auditor 0.17, etc.) map naturally to Black-Litterman "investor views" with confidence weights. This transforms subjective agent ratings into mathematically optimal portfolio weights.

---

## 8. Backtesting Frameworks

| Framework | Stars | Language | Notes |
|-----------|-------|----------|-------|
| **VectorBT** (`polakowo/vectorbt`) | ~4,000 | Python | Vectorized, extremely fast. MaverickMCP uses this. |
| **Backtesting.py** | ~5,500 | Python | Simpler, event-driven. Good for strategy prototyping. |
| **Backtrader** | ~15,000 | Python | Most popular, event-driven, mature. |
| **QuantConnect/LEAN** | ~9,000 | C#/Python | Institutional grade, cloud + local. Large ecosystem. |
| **Zipline** | ~16,000 | Python | Quantopian heritage, less maintained now. |
| **bt** | ~2,500 | Python | Rebalancing/tree-based strategies. |

### Current Gap
No backtesting exists in Investmentology. Paper trading tracks forward performance, but there's no way to validate strategies on historical data.

**Recommendation**:
- **Short-term**: VectorBT (already in MaverickMCP's stack) for quick strategy validation
- **Medium-term**: LEAN/QuantConnect for institutional-grade backtesting with proper slippage, commission models
- **Integration path**: The Quant Gate (Layer 1) produces Magic Formula scores. Backtest: would the top 20 Magic Formula picks each year outperform over 2010-2024? This validates the core thesis.

**Caveat**: Backtesting with yfinance data introduces survivorship bias (only currently-listed companies). Proper backtesting requires point-in-time data (CRSP, Compustat) which are academic/expensive.

---

## 9. Competitor Analysis: AI Investment Platforms

### What They Offer

| Platform | AI Features | Unique Capabilities | Pricing |
|----------|-------------|---------------------|---------|
| **Bloomberg Terminal + BQNT** | GPT-4 integration (BloombergGPT), document Q&A | Real-time unparalleled data, news, terminal | $24,000/yr |
| **Morningstar** | Moat ratings, AI-generated summaries | Deep fundamental analysis, quantitative ratings | $200/yr consumer |
| **Simply Wall St** | Automated equity story, visual risk/reward | Snowflake visual, fundamental storytelling | $35/mo |
| **TipRanks** | Analyst consensus, news sentiment, insider tracking | Crowdsourced analyst ratings, 97-point Smart Score | $30/mo |
| **Koyfin** | Natural language queries, custom dashboards | Data aggregation, Bloomberg-lite | $59/mo |
| **Seeking Alpha** | Quant ratings + author ratings + news | Earnings transcripts, SA Premium quant model | $40/mo |
| **Finviz** | Stock screener, technical filters | Fast visual screener, sector maps | Free / $40/mo |
| **OpenBB** | Open source, agent-based research | 200+ data connectors, Copilot integration | Open source |

### Key Lessons from Competitors

1. **Simply Wall St's "Snowflake"**: Visual multi-factor scoring (Value, Future, Past, Health, Dividends) is extremely user-friendly. Investmentology's layer verdicts could be visualized similarly.

2. **TipRanks Smart Score**: Aggregates 7 signals (analyst consensus, hedge fund activity, insider trading, news sentiment, financial blogging, crowd wisdom, technical analysis) into a 1-10 score. Architecturally similar to Investmentology's synthesis, but without the LLM reasoning layer.

3. **Seeking Alpha Quant**: Combines 5 factor scores (Valuation, Growth, Profitability, Momentum, Revision) with a 0-5 rating. The "SA Premium" layer adds author analysis. Investmentology's multi-agent system provides deeper LLM reasoning but lacks the factor-score transparency.

4. **OpenBB Copilot**: Open source AI assistant for financial research, uses function calling to query 200+ data sources. Most aligned with Investmentology's architecture. No LLM agent debate system, but excellent data infrastructure.

5. **Koyfin's NLP screener**: Allows natural language stock screening ("find tech companies with >30% revenue growth and positive free cash flow"). This is an interface feature worth adding to the PWA.

### Competitive Positioning
Investmentology's differentiation:
- Multi-LLM agent debate (no competitor does this)
- Named investor personas (Warren, Klarman, etc.) for interpretability
- Adversarial Munger layer (bias checking) — unique
- Open/self-hosted (no SaaS cost, private portfolio data)
- Weaknesses: No real-time data, no earnings transcripts, no alternative data, no backtesting

---

## 10. Neo4j Knowledge Graph for Companies

### Use Case
Map supplier/customer/competitor relationships to enhance analysis context. For example:
- NVIDIA → customer: TSMC supplier relationship
- Apple → major supplier: Foxconn, TSMC
- A supply chain disruption at TSMC affects NVIDIA, Apple, AMD, Qualcomm

### Available Data Sources for Graph Population
| Source | Data | Access |
|--------|------|--------|
| **SEC 10-K Risk Factors** | Customer concentration, key suppliers | Free (EDGAR/edgartools) |
| **Bloomberg Supply Chain** | Comprehensive graph | $24K/yr |
| **Refinitiv Supply Chain** | Comprehensive | Expensive |
| **OpenSecrets** | Government contracts, lobbying | Free API |
| **Knowledge Graph Embedding** | Auto-extract from 10-K text | NLP required |

### Implementation Approach

Neo4j is already in the Kernow stack (knowledge MCP). The feasibility of building a company relationship graph:

**Phase 1 (Free)**:
- Extract customer/supplier mentions from 10-K filings using edgartools + LLM extraction
- Manual curations of key sectors (semiconductors, automotive, defense)
- Load into Neo4j as `Company` nodes with `SUPPLIES_TO`, `COMPETES_WITH`, `CUSTOMER_OF` relationships

**Queries that would enhance analysis**:
```cypher
// Find all companies exposed to TSMC supply chain risk
MATCH (tsmc:Company {ticker:'TSM'})<-[:SUPPLIES_TO]-(supplier)
RETURN supplier.name, supplier.ticker

// Find competitors affected by the same macro factor
MATCH (c:Company {ticker:'NVDA'})-[:COMPETES_WITH]-(competitor)
RETURN competitor.name, competitor.ticker
```

**Assessment**: High value for context enrichment in the Competence Filter (Layer 2) and agent analysis (Layer 3). The Soros agent (macro focus) would particularly benefit from supply chain exposure data. Implementation is feasible using edgartools + GPT-4 extraction at ~$10-50 total compute cost. **Medium-term priority.**

---

## 11. What's Missing vs. What's Available Summary

### Critical Gaps (High Impact, Feasible)

| Gap | Tool | Effort | Cost |
|-----|------|--------|------|
| Earnings transcript analysis | OctagonAI MCP | Low (MCP config) | Free |
| Better SEC EDGAR parsing | edgartools | Low (pip install) | Free |
| Portfolio risk metrics | empyrical + pyfolio | Low | Free |
| Position sizing math | PyPortfolioOpt | Medium | Free |
| Alternative data (insider trades) | edgartools Form 4 | Low | Free |
| Alternative data (Congressional) | Quiver Quantitative API | Low | Free |
| Technical indicators on candidates | TA-Lib / pandas-ta | Low | Free |
| Strategy backtesting | VectorBT | Medium | Free |

### Notable Absences (Lower Priority)

| Feature | Reason to Defer |
|---------|-----------------|
| Bloomberg/Refinitiv data | $24K/yr, not justified for paper trading |
| Real-time tick data | Day trading not the use case |
| Brokerage MCP | No MCPs exist; Alpaca SDK is sufficient |
| QuantConnect LEAN | Overkill until basic backtesting is validated |
| FinBERT NLP | Nice to have; agents already read news qualitatively |
| Company knowledge graph | High value but build after core pipeline stabilizes |

---

## 12. Priority Recommendations

### Tier 1 — Immediate (Low effort, high value)

**1. Add OctagonAI MCP**
- Free MCP server with earnings transcripts + private market data + SEC filings
- Configure in `.mcp.json` for the Claude Code context on HB LXC
- Agents (especially Klarman/Auditor) can query earnings transcripts directly
- Adds qualitative depth missing from current yfinance-only data
- URL: https://github.com/OctagonAI/octagon-mcp-server

**2. Replace EDGAR raw calls with edgartools**
- `pip install edgartools`
- Structured XBRL extraction: balance sheet, income statement, cash flows as DataFrames
- Improve Layer 1 fundamentals quality (supplement flaky yfinance data)
- Extract Form 4 insider transactions systematically
- URL: https://github.com/dgunning/edgartools

**3. Add empyrical + pyfolio for Layer 6 (Learning)**
- Compute Sharpe, Sortino, max drawdown on paper portfolio decisions
- Generate tear sheets for the PWA dashboard
- Direct feedback loop for calibration

**4. Add Quiver Quantitative API for Congressional trading**
- Free API, ~20 API calls/day on free tier
- Congressional stock trades are legally required to be disclosed within 45 days
- Known alpha signal: congressional portfolios outperform SPY over time
- Add as a data enrichment step in Layer 2 (Competence Filter)

### Tier 2 — Medium-term (Moderate effort, high value)

**5. PyPortfolioOpt for Black-Litterman Position Sizing**
- Map agent confidence scores → Black-Litterman views
- Produces mathematically optimal portfolio weights vs. current Kelly-based sizing
- Requires 6-12 months of agent verdicts to calibrate view uncertainty
- URL: https://github.com/PyPortfolio/PyPortfolioOpt

**6. VectorBT Backtesting for Quant Gate Validation**
- Backtest Magic Formula top-20 picks across 2015-2024
- Validate that the screening methodology actually produces alpha
- Use yfinance data for historical OHLCV (imperfect but usable for validation)
- URL: Already in MaverickMCP stack

**7. Technical Analysis Layer (TA-Lib or pandas-ta)**
- Add RSI, MACD, Bollinger Bands, ATR to the data available to Simons agent (quant)
- Currently Simons has no quant data beyond fundamentals — this is a gap given its quant persona
- MaverickMCP's source code has 20+ indicator implementations to reference

### Tier 3 — Long-term (High effort, high value)

**8. Company Knowledge Graph in Neo4j**
- Extract supplier/customer/competitor from 10-K filings using edgartools
- Build Neo4j graph in the existing knowledge infrastructure
- Feed relationship context to agents in Layer 3

**9. OpenBB Integration**
- OpenBB (62,709 stars) is the most comprehensive open-source financial data platform
- Would replace yfinance + EDGAR + Finnhub + FRED with a single unified interface
- Major integration effort but provides access to 200+ data connectors
- Wait until OpenBB stabilizes their AI agent interface (in active development)

**10. Custom Finance MCP for Investmentology**
- Build a domain-specific MCP exposing pipeline data to agents
- Tools: `get_pipeline_state`, `get_agent_verdicts`, `get_paper_portfolio`, `run_quant_gate`
- Would allow agents on HB LXC to query live pipeline state via MCP calls
- Follows the same pattern as the other domain MCPs in the homelab

---

## Links Reference

| Resource | URL | Stars |
|----------|-----|-------|
| MaverickMCP (finance MCP server) | https://github.com/wshobson/maverick-mcp | 405 |
| OctagonAI MCP (earnings + private data) | https://github.com/OctagonAI/octagon-mcp-server | 103 |
| Yahoo Finance MCP | https://github.com/Alex2Yang97/yahoo-finance-mcp | 234 |
| edgartools (SEC EDGAR Python) | https://github.com/dgunning/edgartools | 1,802 |
| sec-api-python (already in stack) | https://github.com/janlukasschroeder/sec-api-python | 286 |
| PyPortfolioOpt | https://github.com/PyPortfolio/PyPortfolioOpt | 5,530 |
| Riskfolio-Lib | https://github.com/dcajasn/Riskfolio-Lib | 3,804 |
| OpenBB | https://github.com/OpenBB-finance/OpenBB | 62,709 |
| alpaca-py (already in stack) | https://github.com/alpacahq/alpaca-py | 1,168 |
| ib_async (Interactive Brokers) | https://github.com/ib-api-reloaded/ib_async | 1,402 |
| awesome-mcp-servers | https://github.com/appcypher/awesome-mcp-servers | 5,220 |
| awesome-claude-code-plugins | https://github.com/ccplugins/awesome-claude-code-plugins | 613 |
| Alpha Vantage Python wrapper | https://github.com/RomelTorres/alpha_vantage | 4,744 |
| fredapi (FRED economic data) | https://github.com/mortada/fredapi | 1,126 |

---

*Generated by tools-researcher agent as part of Deep Review series. See also: `research/data-gathering.md`, `research/broker-firms.md`*
