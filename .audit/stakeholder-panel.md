# Stakeholder Panel: What Different Users Need

Five personas evaluate the PWA through their lens, informed by the gap analysis. Each persona identifies what they want to see, what confuses them, and how they'd interpret the platform's unique value.

---

## Persona 1: Sarah — Institutional Portfolio Manager (20yr experience)

**Background**: Manages $500M multi-cap equity fund. Bloomberg terminal daily. Reads 10-Ks for fun. Used to multi-factor models, risk analytics, and sell-side research.

### What She Values
- **The advisory board is the killer feature** — having 8 distinct investment philosophy lenses on every stock is what sell-side research charges $50K/year for. But she can only see 140-char `assessment` snippets. She needs the full `reasoning` field (2-3 sentences per advisor). That's where the differentiated analysis lives.
- **Agent accuracy matters more than agent count** — she doesn't care that there are 9 agents. She cares which ones are *right*. The Attribution data (per-agent accuracy, bullish/bearish splits) should be front and center, not buried in a Learning tab.
- **Consensus score needs context** — "0.72 consensus" means nothing without showing the distribution. She wants to see: "6 bullish, 1 neutral, 2 bearish — Warren, Klarman, Dalio bullish; Auditor cautious; Simons bearish." The WHO matters as much as the number.

### What She'd Change
1. **Deep Dive: Show full advisory board reasoning** — expand each advisor card to show the `reasoning` field, not just `assessment`. Group advisors by vote (Approve/Adjust/Veto) so she can quickly scan the bull vs bear arguments.
2. **Add agent target price range** — "Fair value range: $120 (Klarman, margin-of-safety) to $165 (Druckenmiller, momentum premium), median $142." This is standard institutional format.
3. **Surface the pre-mortem prominently** — "What Would Make Us Wrong" is the first thing institutional investors look for. The pre-mortem and kill scenarios should be *above the fold* on the risk panel, not hidden or ephemeral.
4. **Show decision settlement** — "Of our last 20 BUY calls, 14 were profitable after 6 months." Track record is how she builds trust in any system.
5. **Attribution dashboard on the main nav** — not hidden in Learning. "Warren: 73% accuracy (18/25 bullish calls correct), Auditor: 82% on bearish calls (caught 4/5 declines)." This is how she'd weight the opinions.

### What Confuses Her
- Nothing about the financial terms — she knows them all.
- The "Success Probability" ring is unclear — what's the methodology? Is it forward-looking probability or backward-looking accuracy? She'd want the formula breakdown.
- Why the consensus score ranges from -1 to +1 instead of a percentage.

---

## Persona 2: Marcus — Retail Self-Directed Investor (3yr experience)

**Background**: Software engineer who started investing during COVID. Uses Robinhood. Watches a few finance YouTube channels. Knows P/E ratio and dividend yield, fuzzy on most else. Has $80K portfolio.

### What He Values
- **The verdict is the product** — BUY/SELL/HOLD with a confidence number. That's what he's here for.
- **Agent personalities make it engaging** — he likes the idea that "Warren" and "Soros" are debating. But he can't access the debate. He sees colored dots. He needs to *read* the disagreement.
- **Risk section must be scary enough to be useful** — if the system says BUY at 85% confidence but there are 3 kill scenarios, he needs to feel the weight of those scenarios. "What if this company's main customer leaves?" is more impactful than "CUSTOMER_CONCENTRATION" as a tag.

### What He'd Change
1. **Explain every number** — he doesn't know what Piotroski F-Score is. Every financial metric needs a one-line tooltip: "Piotroski F-Score (7/9): Financial health score. 8-9 is excellent, below 3 is concerning."
2. **Replace agent dots with a debate summary** — instead of 9 colored circles, show: "7 of 9 agents say Buy. The 2 dissenters (Auditor, Simons) are worried about [key_concern]." Narrative > visualization for non-experts.
3. **Kill scenarios in plain English** — "How This Could Go Wrong" section with the 5 kill scenarios written as if explaining to a friend. "Scenario 1: Their biggest customer (35% of revenue) switches to a competitor. Likelihood: Medium. Impact: Stock could drop 40%."
4. **"What does this mean for my money?"** — translate verdicts into dollar impact. If he owns 50 shares at $100, and the system says REDUCE, show "Consider selling 20 shares (~$2,000). Here's why:" Not just a badge.
5. **Signal tags need prose** — "MOAT_NARROWING" means nothing to him. Show the `detail` field: "Their competitive advantage in cloud services is eroding as AWS and Azure gain market share in the SMB segment."

### What Confuses Him
- **Sharpe ratio, Sortino ratio, Alpha** — no idea what these mean. Needs "Your portfolio is beating the market by 3.2% — that's good."
- **Sentiment -1 to +1** — is 0.3 good? Bad? Needs a word: "slightly bullish."
- **Consensus score** — same issue. Needs "Strong agreement" not "0.72."
- **Piotroski, Altman, ROIC** — might as well be hieroglyphics without explanation.
- **"Munger Override"** — who is Munger and why does he override things?

---

## Persona 3: Diana — Quantitative Analyst (8yr experience)

**Background**: PhD in applied math, worked at Two Sigma. Builds factor models. Cares about data integrity, backtesting, calibration. Uses Python and R daily.

### What She Values
- **Calibration data is the entire point** — she needs to know: when the system says 80% confidence, is it right 80% of the time? The Brier score and calibration buckets exist in Learning view but are buried. This should be *the* trust metric.
- **Agent weight optimization** — the Attribution endpoint returns recommended weight adjustments. This is the feedback loop that makes the system improve. She wants to see current weights vs recommended weights and understand why.
- **Signal taxonomy is impressive** — 102 signal tags across 6 categories is a real taxonomy. But she can't see signal frequency, co-occurrence patterns, or which signals predict returns. The data is there in agent_signals.

### What She'd Change
1. **Calibration chart on dashboard** — not buried in Learning. A small reliability diagram: "When we say 70% confident, we're right 68% of the time." This is the headline trust metric.
2. **Show the signal detail prose** — clicking any signal tag should reveal the `detail` field. She wants to audit the reasoning, not just the label.
3. **Agent performance comparison** — side-by-side accuracy table: Agent | Bullish Accuracy | Bearish Accuracy | Total Calls | Recommended Weight. Available from `/learning/attribution` but not prominently displayed.
4. **Pendulum decomposition** — show the component scores (VIX, put/call, SPY momentum) not just the aggregate. She wants to see what's driving the fear/greed reading.
5. **Earnings momentum components** — show `upwardRevisions` and `downwardRevisions` counts, not just the label. "3 analysts raised estimates, 1 lowered" is data. "UPWARD" is a label.
6. **Historical accuracy per verdict tier** — "When we've previously rated stocks STRONG_BUY, they returned +18% on average over 6 months (n=15)." This is backtesting the recommendations.
7. **Store and display adversarial outputs** — kill scenarios with likelihood/impact/timeframe is exactly the kind of structured risk analysis she'd incorporate into a factor model.

### What Confuses Her
- Nothing about the math — she'd want more of it.
- Frustrated that `decision.outcome` and `settledAt` are in the schema but not displayed. Predictions without settlement are worthless.
- The Success Probability formula should be documented and visible.

---

## Persona 4: James — Retired Financial Advisor (35yr experience, semi-retired)

**Background**: Former Merrill Lynch FA, managed $200M book of high-net-worth clients. Now manages his own $2M retirement portfolio. Conservative, income-focused. Reads Barron's.

### What He Values
- **Income analysis** — dividend yield, growth, payout ratio, ex-dates, frequency. The platform has `div_growth_5y`, `payout_ratio`, `last_div_date` in the backend but doesn't surface them. He'd build his whole strategy around these.
- **Risk management over returns** — he's not trying to beat the market. He wants to not lose money. The pre-mortem and kill scenarios are more important to him than the BUY recommendation.
- **Thesis health monitoring** — he buys and holds for years. The thesis lifecycle (INTACT → UNDER_REVIEW → CHALLENGED → BROKEN) is exactly how he thinks. But `heldPosition.reasoning` (the WHY behind health changes) isn't shown.
- **Portfolio balance** — sector concentration, risk exposure by category. The balance section exists but is collapsed by default.

### What He'd Change
1. **Dividend deep-dive** — separate section showing: yield, 5-year growth rate, payout ratio, ex-date, frequency, annual income from position. All this data exists backend but isn't fully surfaced.
2. **"What's Changed Since I Bought" view** — thesis events timeline showing: entry thesis, each reaffirmation or challenge, current verdict vs entry verdict, key risks that emerged. The `/portfolio/thesis/{ticker}` endpoint exists but isn't prominent.
3. **Income projection** — "At current dividend rates, this portfolio generates $X/month." The dividend summary exists but could be more forward-looking.
4. **Risk dashboard as primary tab** — he'd make the Risk tab the first tab on Portfolio, not the third. Show concentration warnings, drawdown alerts, and sector imbalances from the daily briefing.
5. **Simpler language throughout** — instead of "Consensus Score: 0.72", say "Strong agreement among analysts (7 of 9 positive)." Instead of "Alpha: 3.2%", say "Your portfolio is returning 3.2% more than the S&P 500."

### What Confuses Him
- He knows most financial terms but finds the agent-specific jargon confusing: "Reflexivity detected" (Soros concept), "All-weather analysis" (Dalio concept).
- The sentiment scale (-1 to +1) should be words: Bearish, Lean Bear, Neutral, Lean Bull, Bullish.
- The number of views/tabs feels overwhelming — he'd want a simpler dashboard focused on "is my portfolio healthy? do I need to do anything?"

---

## Persona 5: Tom — Intelligent Layperson (0yr investing experience)

**Background**: Marketing director, 42, makes good money, has $150K sitting in a savings account earning nothing. His wife told him to start investing. Has read "The Intelligent Investor" halfway through. Understands compound interest conceptually but has never bought a stock.

### What He Values
- **Trust signals** — he's terrified of losing money. He needs to know WHY the system recommends something, in language he can understand. "9 AI agents analyzed this stock" means nothing. "We asked 9 different investment analysts, each with a different strategy, to independently evaluate Apple. 7 said buy, here's why" — that's trust.
- **The bear case** — he specifically wants to know what could go wrong BEFORE he buys. The kill scenarios and pre-mortem are THE feature for him, but they're not shown.
- **Plain English everything** — no acronyms, no ratios, no scores. Just: "This company makes $X selling Y. They're growing at Z%. Our analysts think the stock price should be higher."

### What He'd Change
1. **Onboarding glossary** — first time he sees "P/E Ratio: 24.5x", he needs a popup: "Price-to-Earnings ratio. You're paying $24.50 for every $1 of the company's annual profit. The market average is ~20x, so this is slightly above average."
2. **Verdict as a story, not a badge** — instead of "BUY — 82% confidence", show: "Our team recommends buying Apple. Here's the argument: [2-paragraph narrative from boardNarrative.narrative]. Some of our analysts disagree: [conflict_resolution]. The main risk: [risk_summary]."
3. **"How could I lose money?"** section — using kill scenarios: "Here are 5 ways this investment could go wrong, ranked by likelihood." This is the most accessible way to present risk.
4. **Remove jargon entirely for a "simple mode"** — Piotroski → "Financial Health: Strong (7/9)". Altman Z → "Bankruptcy Risk: Very Low". ROIC → "Return on Money Invested: 22% (good is >15%)". Every metric gets a human translation.
5. **Portfolio impact preview** — before adding a position, show: "If you buy $5,000 of Apple, your portfolio would be: 60% tech, 20% healthcare, 20% cash. Recommendation: This would increase your tech concentration. Consider diversifying."
6. **Agent analysis as a panel discussion** — instead of colored dots, present agent views as a conversation: "Warren (value investor): 'Apple's brand loyalty creates a moat...' Soros (macro analyst): 'Rising rates could pressure tech valuations...' Auditor (risk analyst): 'Watch the China revenue exposure...'" Use their actual `summary` text.

### What Confuses Him
- **Everything** — every financial term needs explanation. He doesn't know what a sector is, what market cap means, what P/E is, what a dividend is in practical terms.
- The number of views is overwhelming — he needs a "What should I do today?" answer, not 10 tabs of data.
- Agent names (Warren, Klarman, Soros) mean nothing to him — he doesn't know these are legendary investors. Needs "Warren (inspired by Warren Buffett, focuses on finding great companies at fair prices)."
- Success Probability ring looks important but he has no idea what goes into it.

---

## Synthesis: Common Themes Across All 5 Personas

### 1. Show the Advisory Board's Full Reasoning (ALL personas)
Every persona wants more than the 140-char `assessment`. The `reasoning` field is the differentiated content. Sarah wants it for philosophy comparison, Marcus for understanding the debate, Diana for auditing, James for risk assessment, Tom for trust.

### 2. Surface the Adversarial Content (ALL personas)
Kill scenarios and pre-mortem are universally valued. They're the most compelling content the system produces — and currently ephemeral. Must be stored and prominently displayed.

### 3. Explain Financial Terms (4/5 personas)
Only Diana doesn't need this. Every metric needs a human-readable tooltip. Consider a "Simple Mode" toggle that replaces jargon with plain English throughout.

### 4. Agent Target Price Range (3/5 personas)
Sarah, Marcus, and James want to see the range of fair values from different agents. "Our analysts see fair value between $X and $Y" is universally understood.

### 5. Show Signal Detail Prose (3/5 personas)
The `detail` field on each signal tag explains WHY in the agent's words. Currently hidden — should be one click away.

### 6. Decision Track Record (3/5 personas)
Sarah, Diana, and James want to see: "When we said BUY, were we right?" The `outcome` and `settledAt` fields exist but aren't rendered.

### 7. Pendulum Decomposition (2/5 personas)
Diana and James want to see what drives the fear/greed gauge, not just the number. Components are available but not shown.

### 8. Present Agent Views as Narrative, Not Just Visuals (2/5 personas)
Marcus and Tom want to READ the debate, not infer it from colored dots. The agent `summary` fields are available but buried behind multiple clicks.

---

## Priority Implementation Matrix

| Feature | Effort | Impact | Personas Served | Priority |
|---------|--------|--------|-----------------|----------|
| Show full advisory `reasoning` | Low (data exists) | High | ALL 5 | **P0** |
| Store + show adversarial content | Medium (DB + API + UI) | Very High | ALL 5 | **P0** |
| GlossaryTooltip on all metrics | Medium (component exists) | High | 4/5 | **P0** |
| Agent target price range | Medium (API + UI) | High | 3/5 | **P1** |
| Signal detail prose on click | Low (data exists) | Medium | 3/5 | **P1** |
| Decision outcome display | Low (field exists) | Medium | 3/5 | **P1** |
| Agent narrative summary accessible | Low (rearrange UI) | High | 2/5 | **P1** |
| Pendulum component breakdown | Low (data exists) | Medium | 2/5 | **P2** |
| Calibration chart on dashboard | Low (component exists) | Medium | 2/5 | **P2** |
| Attribution dashboard prominent | Medium (new layout) | Medium | 2/5 | **P2** |
| Dividend deep-dive section | Medium (data partially exists) | Medium | 2/5 | **P2** |
| Simple mode / jargon toggle | High (dual UI layer) | High | 2/5 | **P3** |
| Portfolio impact preview | High (new calculation) | Medium | 1/5 | **P3** |
