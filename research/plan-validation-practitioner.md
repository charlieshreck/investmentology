# Practitioner Validation: Investmentology Roadmap

*Reviewer: Senior Portfolio Manager perspective*
*Date: 2026-03-09*
*Sources: All 14 research documents + CLAUDE.md architecture review*

---

## Who Is This System Closest To?

The honest answer: **none of the four models cleanly, and that is a problem**.

**Bridgewater** (systematic macro): Bridgewater builds rules-based systems with no human discretion. Every decision goes through the system. Investmentology aspires to this — the pipeline is deterministic, the agents are consistent — but the underlying models are LLMs responding to narrative prompts. That is not systematic. It is structured discretion. A Bridgewater-style system would not have a "Warren Buffett persona" who "knows he's Buffett." It would have econometric models for debt cycle positioning, yield curve signals, and cross-asset correlations expressed in code. The philosophical DNA is wrong.

**AQR** (systematic value + momentum): AQR is the closest match to Investmentology's core. The Magic Formula quant gate, the Piotroski/Altman scoring, the momentum factor — these are AQR's building blocks. But AQR trades across thousands of stocks at small positions with tight factor exposures. Investmentology is trying to concentrate into 10-20 high-conviction ideas. That is not AQR. AQR doesn't run concentrated portfolios with narrative-driven agents for individual stock stories.

**Baupost** (deep value, Klarman): The emphasis on margin of safety, the adversarial layer, the thesis-based sell discipline, the cash-as-a-weapon thinking — these are Baupost. But Baupost has a 40-person analyst team producing proprietary research on deeply complex situations. The edge is in information asymmetry on obscure, institutionally-restricted securities. Investmentology is running yfinance on S&P 500 companies that 10,000 analysts already cover. The Baupost ethos applied to large-cap, heavily-researched stocks with free public data is not Baupost.

**Renaissance** (pure quant): Simons is in the system for brand reasons only. The actual Simons agent produces retail-level RSI/MACD signals. This has been correctly identified as wrong by the deep review. The real Renaissance operates with massive datasets, millisecond execution, and proprietary signals across thousands of instruments. Nothing about Investmentology is Renaissance.

**What Investmentology actually is**: A sophisticated retail investor's decision-support tool, aiming to impose institutional discipline on a 10-20 stock concentrated portfolio. That is a legitimate and valuable goal. But the research documents consistently oversell it as "institutional-grade" when it is not, and that framing leads to poor prioritization choices. The right comparator is not Bridgewater or Renaissance — it is a very well-run family office or a single experienced PM managing their own capital.

**This framing matters for the roadmap**: if the target is family-office quality for a single informed investor, some planned features are appropriate, others are severe overkill, and some genuinely important things are missing.

---

## What Do Real PMs Need Monday Morning?

I'll rank the roadmap items by what actually changes behavior and protects capital.

### Tier 1 — I need this before markets open (or I make worse decisions without it)

**1. Current portfolio status with thesis health per position**
Not a score. Not an agent verdict. The single answer to: "Is this thesis still intact? And has anything happened since Thursday that I need to act on?" Real PMs arrive Monday morning, scan their book, and look for anything that broke over the weekend. The current briefing exists but is described as "data tables" rather than narrative alerts. This is the highest-priority communication improvement. The roadmap's C2 (newsletter briefings) and A3 (thesis monitoring with alerts) are both in Tier 1 — but they are framed as Phase 2 improvements. They should be Phase 0 alongside the bug fixes.

**2. Earnings calendar for the next two weeks**
Every position manager knows which holdings have earnings in the next 10 days. You size differently before earnings. You do not add to a position the week before earnings unless you have very high conviction. You may trim to manage binary event risk. B3 (earnings calendar) is in Phase 2 — it should be in Phase 1. Before any quant gate improvement.

**3. What is cash at right now, and is it enough?**
Klarman held 30-50% cash at Baupost during expensive markets. The system tracks cash as a position but doesn't surface the opportunity cost question or the "dry powder" framing prominently. If the system is saying "nothing to buy at today's valuations," cash should be presented as the right answer, not a failure state.

### Tier 2 — I check this at least once a week

**4. Which positions are approaching 12-month holding threshold?**
Tax treatment matters enormously for a retail investor. Not for a fund (different tax rules), but for any individual. C7 (tax-aware indicators) is in Phase 1 but de-prioritized as "Low" impact. For a real retail investor managing their own capital, the difference between short-term and long-term capital gains rates (in the US, 10-37% vs. 0-20%) on a winning position can be larger than any alpha the system generates. This is Tier 2 for behavior, and Phase 1 is the right time to do it.

**5. Where am I vs. my benchmark?**
Real PMs track performance vs. SPY. Not to benchmark-hug, but to answer: "Am I generating alpha for the risk I'm taking?" The roadmap barely mentions this. It appears in the theory validation as a "Tier 1 Critical Gap" but is not in the application plan at all. For a system that has been running for months, knowing whether the selection process is generating alpha vs. just holding beta is essential feedback. This belongs in the decision journal enhancement (C4).

**6. What is on the watchlist and why hasn't it been bought?**
The gap between "we analyzed this and it's a BUY" and "we haven't actually bought it" is where most retail investor alpha is lost. The hesitation zone. A PM would want to see: all stocks with BUY verdicts that are not in the portfolio, the reason they aren't (valuation too rich since verdict? sizing concerns?), and whether the thesis has evolved. This is not in the roadmap at all.

### Tier 3 — Useful for deeper analysis but not Monday morning

- Composite quality score (A1) — useful for initial screening, less useful for ongoing monitoring
- Macro regime dashboard (B1) — useful for portfolio posture but not daily decision-making
- Insider activity (B2) — worth checking but not daily
- Quant gate improvements — important for correctness but not what a PM opens first

**The roadmap's prioritization problem**: Phase 1 is loaded with analytical improvements (Beneish, contrarian trigger, momentum disagreement). Phase 2 has the communication improvements that a PM actually uses every day (briefings, thesis monitoring). The ordering is backwards. Build the cockpit first, then refine the engine.

---

## The Sell Problem

This is the most important question in the entire roadmap, and the research has it right: sell discipline is where retail investors leave most of their money on the table. But the research reaches this conclusion via the academic literature. Let me give the practitioner answer.

**How real funds solve sell discipline**:

At the PM level, it is never software. It is always process, and the process is usually one of:

1. **Thesis invalidation review at earnings**: Every quarter, after every earnings report, every analyst must affirm or modify the thesis. If they cannot articulate why the original thesis is still intact, the position goes on the "at risk" list and the default is to trim. Software doesn't do this. A trained analyst who knows the company does this. The software equivalent — the "Would you buy today?" periodic prompt — is a reasonable approximation, but it must be treated as a mandatory decision gate, not an optional notification.

2. **Hard position limits and forced review at breach**: Most funds set maximum position weights (5%, 7%, 10%). When a winning position reaches the limit through appreciation, there is a mandatory review: is this still our best risk-adjusted opportunity? More often than not, the answer is no, because something has already changed (P/E has expanded, sector has gotten crowded). The review itself forces a decision. This is different from an algorithm detecting fair value — it's a process trigger.

3. **Opportunity cost comparison at quarterly review**: The question is not "should I sell?" but "if I had this cash today, would I buy this stock or something else?" This reframing eliminates anchoring to cost basis. It's the "Would you buy today?" test, but it needs to be done at a specific time (quarterly portfolio review) with the watchlist visible for comparison.

**What actually works and what doesn't**:

*Works*: Thesis-based exits with pre-defined invalidation criteria. But the criteria must be written at entry, not retroactively. If you write them after the stock has dropped 30%, you're writing criteria that justify what you've already done (confirmation bias). The app correctly identifies this as critical. The implementation must force criteria entry at buy time.

*Works*: Valuation ceilings. "I bought this at 15x earnings. If it reaches 25x without earnings growing proportionally, I trim." This is mechanical and removes the psychology from the decision.

*Doesn't work*: Stop-losses for value investors. Buffett famously says he'd rather buy more if a stock he owns drops 20% and nothing has changed. A hard stop-loss on a long-duration value thesis creates noise-driven exits. This conflicts with the theory validation's recommendation to add stop-loss logic. The resolution: stop-losses should be thesis-dependent, not price-only. For "PERMANENT" position type, stop-loss should only trigger if thesis is also CHALLENGED or BROKEN. For "TACTICAL" type, a price stop is more appropriate because the time horizon is shorter and the thesis less durable.

*Doesn't work*: Algorithmic sell signals without human review gate. If an agent produces SELL and the system surfaces it prominently enough to cause immediate action, you get whipsaw. The sell signal should be: "A threshold has been crossed. This requires your review." Not: "Sell this." The distinction is fundamental.

**Roadmap assessment on sell discipline**: The thesis-based sell system (A3) is correctly identified as the highest-priority item in the whole roadmap. The position lifecycle management (A4) adds valuable staged trimming logic. These are right. The only addition I'd make: force invalidation criteria entry at buy time. Make it impossible to record a buy without at least one quantifiable and one qualitative invalidation criterion. Without this forcing function, the system accumulates positions with vague theses that are never challenged.

---

## Portfolio Construction: Is Black-Litterman Overkill?

Yes. For a 10-20 position portfolio, Black-Litterman is a solution to a problem that doesn't exist at this scale.

**Why B-L exists**: B-L was invented by Goldman Sachs in 1990 to solve a specific problem in institutional portfolio optimization — Markowitz optimization is brutally sensitive to return estimates, and small errors in expected returns produce extreme corner solutions (100% in one stock). B-L stabilizes this by combining the market equilibrium as a prior with the PM's views expressed as deviations from equilibrium. It's elegant and it works at 200+ stocks where optimization actually matters.

**Why it doesn't matter at 10-20 positions**:

At 10-20 positions, you already have what B-L is trying to give you: concentrated portfolio with a few high-conviction views. If you have 15 positions and you believe in 12 of them strongly and 3 moderately, simple conviction weighting is better. Put 8-9% in your high-conviction ideas, 5-6% in moderate conviction, and keep the rest in cash. The math of B-L with a 15-stock portfolio and LLM-generated "expected return estimates" will optimize to something very close to what an experienced PM's gut says — and the gut has the advantage of being intelligible.

**The real portfolio construction problem at this scale**:

It's not optimization. It's avoiding hidden correlation. The portfolio concentration risk at 15 positions is not that weights are suboptimal — it's that you think you have 15 uncorrelated ideas but you actually have 6 technology theses, 3 industrials, 2 healthcare, and 4 financials, and 4 of your tech positions all correlate 0.75 with each other. During a sector rotation out of tech, your "15-stock diversified portfolio" behaves like a 3-stock portfolio.

The Portfolio-Level Analytics Dashboard (C3) addresses this correctly by adding sector concentration heatmap and correlation matrix. That is the right priority — not B-L. The roadmap synthesis document identifies C3 as a high-impact item in Phase 3. Given the above, it should be Phase 2.

**Conviction weighting in practice**:

The simplest correct approach for 10-20 positions:

- **Full position** (8-10%): You've done full analysis, thesis is clear, margin of safety is there, you've already had one positive quarter confirmation. Maximum 3 positions at this size.
- **Core position** (5-7%): Standard allocation for a confirmed thesis. This is your average holding.
- **Starter position** (2-3%): Initial entry while you continue research, or a thesis you believe but haven't fully confirmed. Maximum 4-5 positions here.
- **Cash** (15-30%): Not a failure. If the system finds only 4 high-conviction ideas in the current market, that's the right answer. Forcing full deployment into 15 mediocre ideas is worse.

The position lifecycle management (A4) captures this correctly with STARTER/BUILDING/FULL/TRIMMING stages. This is good. The application plan gives it medium-high impact in Phase 3. Given that it's the operational mechanism for conviction weighting, it should be Phase 2.

---

## Agent Accuracy: Does Faithfulness to Real Investors Matter?

This is the most intellectually interesting question in the validation. My answer: **partial fidelity matters more than complete fidelity, and the question itself is somewhat wrong**.

**What the research gets right**: Simons (3/10 accuracy) is a liability. Not because he uses RSI/MACD instead of Renaissance-style quant — LLMs cannot actually do Renaissance-style quant anyway. The problem is that the Simons agent is a poor-quality signal that masquerades as a quantitative voice. A low-quality RSI/MACD technical analyst does not add useful signal diversity; it adds noise. Correct the persona to "pure momentum/mean-reversion check with explicit abstention when no statistical signal" and the agent becomes useful.

**What the research gets wrong**: For most agents, persona fidelity matters less than prompt engineering for what you actually want. "Warren Buffett" as a persona helps the LLM focus on the right kinds of questions — moat durability, management quality, normalized earnings power. Whether the Warren agent uses exactly Buffett's "owner earnings" formula or a close approximation is less important than whether the agent is asking hard qualitative questions about competitive advantage. The specific Buffett methodology points (DCF vs. mental multiples, newspaper test, franchise vs. commodity distinction) that the deep review flags as missing are refinements, not fundamentals.

**The "wrong Simons adding signal diversity" question**:

A poorly-specified Simons adding RSI/MACD signals does add diversity — in the sense that RSI/MACD occasionally produces signals that the value agents don't generate. But this is noise diversity, not signal diversity. The key test for whether an agent is adding value is not whether it's different, but whether it's different *and right* more than chance. An agent that randomly says BUY or SELL with 50/50 odds adds diversity but destroys the calibration system. The value of the Simons agent depends entirely on whether momentum persistence (correctly implemented as J-T 12-1 month) actually adds predictive value beyond what the other agents see.

**Academic evidence on this**: Momentum (12-1 month) genuinely works as a factor. It is one of the most replicated findings in empirical finance (Fama and French acknowledge it even though it contradicts their pure value framework). A correctly-implemented momentum signal in the Simons role would add genuine uncorrelated value to the value-heavy agent team. The current RSI/MACD version probably doesn't.

**The Howard Marks gap**: This is the one genuinely missing agent perspective that matters in practice. Marks's "second-level thinking" framework — "not what is good, but what does the market believe is good, and is the market right?" — is the most important question in active management. It is the question that distinguishes alpha from beta. None of the current agents explicitly ask it. Warren asks "is this business good?" Klarman asks "is this cheap?" Marks asks "does the market know it's cheap, and if so, why isn't it correcting?" That is a different question and it deserves a dedicated voice.

---

## Risk Management at Retail Scale

**What VaR actually is and why it doesn't matter here**: Value-at-Risk is the expected loss at a given confidence level over a given time horizon. For a $100M+ fund with regulatory reporting requirements, VaR is mandatory. For a 15-stock portfolio, VaR is a number you calculate, display in a dashboard, and ignore when the market is crashing — at which point all VaR models fail anyway because they assume normal distributions and markets crash in fat tails. Historical VaR on a 15-stock portfolio with 2 years of data is not statistically meaningful.

**What actually matters for 10-20 positions**:

1. **Position concentration limit**: No single stock > 10% of portfolio. This is not sophisticated — it is the single most effective retail risk rule. The system has this (max 5% is actually more conservative than I'd suggest — some PMs go to 10% for highest conviction). The enforcement needs to be hard, not just advisory.

2. **Sector concentration limit**: No single sector > 30-35%. This is actionable and protects against sector-specific shocks. The correlation matrix and sector heatmap (C3) addresses this. This is the right risk tool, not VaR.

3. **Cash buffer discipline**: Keep minimum 15-20% cash when market P/E is above historical median, 25-30% when valuation is extended. This is Klarman/Buffett/Marks all agreeing. The system has a 5-35% cash range which is wide enough. The question is whether it explicitly links cash level to valuation regime.

4. **Earnings binary event risk**: Position sizing should be smaller (half of normal) when earnings are less than 2 weeks away. This is not about stop-losses — it's about not having full exposure to a coin-flip event when you don't have an informational edge. B3 (earnings calendar) enables this. It is more important than most of the quant gate improvements.

5. **Correlation in crisis**: The one risk management tool that matters and doesn't exist in the current system is knowing that during a 2008-style crisis, your 15 "diversified" positions will all correlate to 1.0. The portfolio analytics dashboard (C3) shows 60-day rolling correlation under normal conditions. What you actually need for risk management is crisis correlation — what does this portfolio look like during the worst 10% of market months? This requires either stress testing (sector shock scenarios already partially planned in C3) or a simple historical scenario analysis ("In Q4 2022, this portfolio would have fallen X%").

**What the roadmap gets wrong on risk management**:

The theory validation rates Risk Management as "D" and recommends VaR, CVaR, and stop-loss integration. For an institutional fund that is right. For a retail investor with 15 positions, the D-rated system is actually closer to what you want than a full institutional risk framework. The practical improvements are: sector limits, earnings calendar, portfolio correlation heatmap, and a simple historical stress test. VaR is not the right fix.

---

## Top 5 Items from the Entire Roadmap

If I could only pick 5, prioritized by what actually changes decision quality and protects capital:

### 1. Fix the math bugs (Phase 0)

This should not even be called a "roadmap item" — it is correctness. The Greenblatt composite rank bug (mapping median stocks to 0.0 Piotroski score), the Altman manufacturing formula applied to tech companies, and the Piotroski gross margin vs. operating margin confusion are producing wrong screens right now. Every other improvement built on a broken screen is wasted. Fix these before anything else. 1-2 days of work.

### 2. Thesis monitoring with forced criteria at entry (A3, enhanced)

The single highest-impact improvement in the entire system. But with one enhancement the roadmap doesn't fully specify: make it mechanically impossible to record a BUY decision without entering at least one quantifiable invalidation criterion (e.g., ROIC floor, F-Score minimum) and one qualitative criterion (e.g., "thesis breaks if they lose the government contract"). This forcing function is what separates professional discipline from a decision log. Without it, the thesis system becomes another place to store free-text notes that are never acted on.

### 3. Earnings calendar integration with sizing guidance (B3, elevated priority)

Move this to Phase 1, not Phase 2. For every held position and watchlist stock, display days-to-earnings prominently. Add sizing guidance: "Standard position sizing when >30 days to earnings. Reduce to starter position or defer entry when <15 days to earnings." This one change prevents the most common retail mistake: initiating or adding to a position right before a binary event you have no informational edge on.

### 4. Portfolio analytics dashboard — sector heatmap and correlation (C3, core only)

Don't build all of C3 first. Build only two things from it: (a) sector concentration by weight with 30% warning threshold, and (b) pairwise correlation matrix for held positions. Skip the portfolio optimization and Black-Litterman for now. These two simple tools reveal the hidden risk that will end most retail investors' concentrated strategies: you think you're diversified but you're actually a sector fund.

### 5. Monday morning briefing — thesis-first, narrative format (C2)

Not because it generates alpha directly, but because a PM who doesn't read the briefing is flying blind. The current briefing is described as data tables. Data tables don't get read. A well-written briefing that leads with "Three positions have thesis events this week, here's what to watch" followed by "One position's F-Score dropped 2 points, thesis is CHALLENGED" gets read and gets acted on. If the system produces brilliant analysis that nobody reads because it's formatted as a database dump, the entire pipeline is wasted. The communication layer is the leverage point on everything else.

---

## Items That Should Be Deprioritized or Cut

**Black-Litterman portfolio optimization** — overengineered for scale. Replace with the simple conviction-weighting system described above. Saves 1-2 weeks of work.

**Beneish M-Score as composite component** — as an exclusion filter (binary: manipulator or not) this is valuable. As a continuous component of a composite score, it adds complexity without proportional value. The binary version takes one day; the composite version takes more and adds less.

**Backtesting the pipeline** (Phase 4) — valuable eventually, but survivorship bias in yfinance data and look-ahead bias in fundamental data make any backtest misleading until the data infrastructure is significantly improved. Don't invest in backtesting until edgartools or a point-in-time data source is integrated.

**Congressional trading disclosure (Quiver Quantitative)** — 20 calls/day free tier on a pipeline covering 100 stocks is insufficient for systematic use. This is a feature for ad-hoc research, not pipeline integration. The research documents list it as a quick win but the data volume constraint makes it mostly decorative.

---

## Summary Verdict on the Roadmap

The roadmap is technically sound but practically mis-sequenced. It prioritizes analytical improvements (quant gate composites, agent accuracy, additional signals) over operational improvements (briefing format, earnings calendar, thesis entry forcing). Real investment decisions are made in the cockpit, not the engine room. Build the cockpit first.

The five items above — bug fixes, thesis monitoring with forced criteria, earnings calendar with sizing guidance, sector/correlation analytics, and a readable briefing — would transform this from an interesting research prototype into something that could plausibly improve a retail investor's returns. The other 25 items on the roadmap are valuable enhancements to those five foundations.

One honest caution: the most dangerous version of this system is one that is sophisticated enough to generate confident-sounding verdicts but not yet calibrated enough to be trusted. The single most important safeguard against this is the calibration tracking (Layer 6) — and it requires 6-12 months of settled predictions before it means anything. Until that data exists, every verdict the system produces should be presented to the user with appropriate epistemic humility: "This is what nine analytical frameworks suggest. The system has not yet generated enough settled predictions to know whether it is actually right more often than wrong."

---

*Document based on review of all 14 research files at /home/investmentology/research/, CLAUDE.md architecture documentation, and practitioner experience with institutional investment operations.*
