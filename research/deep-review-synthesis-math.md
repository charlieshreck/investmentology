# Deep Review: Synthesis Mathematics and Decision Framework

*Reviewer: Mathematical Statistician Agent*
*Date: 2026-03-08*
*Files reviewed: `src/investmentology/verdict.py`, `src/investmentology/pipeline/convergence.py`, `src/investmentology/agents/debate.py`*

---

## Executive Summary

The synthesis engine has a sound conceptual foundation. The weighted consensus formula is a legitimate aggregation method, imputation is principled, and the auditor veto has reasonable thresholds. The main mathematical weaknesses are: (1) the sentiment formula double-counts information and can exceed intended bounds; (2) the 1.3× sell-side correction is a good-faith guess rather than an empirically derived constant; (3) the 0.85^n correlation discount is structurally correct but the coefficient is arbitrary; (4) HOLD imputation systematically biases results toward the center; (5) the regime adjustment (fear raises buy thresholds) is defensible but contradicts pure contrarian logic in ways that need explicit justification; (6) calibration via isotonic regression requires ~100+ samples per agent which may take months to accumulate. Concrete recommendations for each issue follow.

---

## 1. Sentiment Scoring Formula

### Current Formula

```
raw_sentiment = (bullish - bearish) / (bullish + bearish)
evidence_factor = min(1.0, total_signals / 5.0)
sentiment = raw_sentiment × evidence_factor
```

Where `bullish` and `bearish` are weighted counts: `strong=1.5, moderate=1.0, weak=0.5`.

### Mathematical Analysis

**Range**: `raw_sentiment ∈ [-1, +1]`. With `evidence_factor ∈ [0, 1]`, the final `sentiment ∈ [-1, +1]`. Mathematically bounded. ✓

**Interpretation of the ratio**: This is the **balance statistic** — a standard technique in sentiment analysis (Loughran & McDonald, 2011, "When is a Liability not a Liability? Textual Analysis, Dictionaries, and 10-Ks"). The formula `(pos - neg) / (pos + neg)` normalizes by total signal count, which is correct because different agents may generate different numbers of signals.

**Problem 1: The evidence_factor double-penalizes sparse signals.** When signals are sparse, `raw_sentiment` is already less extreme (it's bounded by the ratio), but `evidence_factor` additionally shrinks the result toward zero. Consider:
- Agent with 2 strong bullish signals: `raw_sentiment = (3.0 - 0) / (3.0) = 1.0`, then `evidence_factor = min(1, 3/5) = 0.60`, so `sentiment = 0.60`.
- Agent with 5 weak bullish signals: `raw_sentiment = (2.5 - 0) / (2.5) = 1.0`, then `evidence_factor = min(1, 2.5/5) = 0.50`, so `sentiment = 0.50`.

The second agent has *more* raw signal mass but gets a *lower* sentiment score. This is counterintuitive and arguably wrong: 5 converging weak signals may be more reliable than 2 strong ones.

**Problem 2: Threshold of 5 is arbitrary.** The docstring says "expected ~5 signals per agent" but this is not calibrated against actual agent output distributions. If agents routinely produce 7-9 signals, then evidence_factor = 1.0 almost always, and the dampening never fires.

**Problem 3: Mixed bullish/bearish are not counted as "neutral".** If an agent produces 3 bullish and 3 bearish signals, `raw_sentiment = 0.0` and `evidence_factor = min(1, 6/5) = 1.0`, so `sentiment = 0.0`. This is actually correct — genuine disagreement signals neutral. ✓

### Better Alternatives

**Option A: Separate the two concerns.** The ratio already handles direction; use evidence scaling only to cap *confidence*, not sentiment.

```python
# Sentiment: pure ratio (already bounded [-1, +1])
sentiment = (bullish - bearish) / (bullish + bearish)

# Evidence factor: scales CONFIDENCE, not sentiment
evidence_factor = min(1.0, total_signals / 5.0)
confidence = agent.confidence * evidence_factor
```

This is cleaner: evidence affects certainty (confidence) but not direction.

**Option B: Smoothed ratio with pseudocounts (Bayesian).**

```python
# Add prior pseudocount of 0.5 to each side (Laplace smoothing)
sentiment = (bullish - bearish + 0.0) / (bullish + bearish + 1.0)
```

The `+ 1.0` denominator dampens extreme ratios when total evidence is low without a separate factor.

**Recommendation**: Adopt Option A. The current formula double-penalizes signal sparsity in a way that can produce unexpected rankings between agents. Separating sentiment and confidence is cleaner and more interpretable.

---

## 2. Weighted Consensus Formula

### Current Formula

```
numerator   = Σ(w_i × corrected_c_i × s_i)
denominator = Σ(w_i × corrected_c_i)
consensus   = numerator / denominator
confidence  = Σ(w_i × raw_c_i) / Σ(w_i)
```

Where `w_i` = base agent weight, `corrected_c_i` = confidence after sell-side bias correction or isotonic calibration, `s_i` = agent sentiment.

### Mathematical Analysis

**What this is**: A confidence-weighted mean, where agents with higher confidence receive more weight in the final average. This is the **Linear Opinion Pool** (LOP) applied to a continuous sentiment variable rather than probabilities.

The LOP was formalized by Stone (1961) and Winkler (1968). It takes the form:
```
p_aggregate = Σ(w_i × p_i)   where Σ(w_i) = 1
```

The system extends this to:
```
s_aggregate = Σ(w_i × c_i × s_i) / Σ(w_i × c_i)
```

This is a doubly-weighted linear combination: base weights `w_i` encode prior beliefs about agent quality; confidence weights `c_i` encode each agent's expressed certainty. This is mathematically equivalent to a linear pool with combined weights `α_i = (w_i × c_i) / Σ(w_j × c_j)`.

### Comparison Against Alternatives

| Method | Formula | Theoretical Properties | Practical Suitability |
|--------|---------|----------------------|----------------------|
| **Current (Linear Pool + confidence)** | `Σ(w_i c_i s_i) / Σ(w_i c_i)` | Coherent, easy to interpret, convergent | Good — defensible choice |
| **Simple linear pool** | `Σ(w_i s_i)` | Well-studied, Bates & Granger (1969) optimality conditions | Slightly simpler; ignores expressed confidence |
| **Geometric mean pool (Log Opinion Pool)** | `∏(p_i^w_i)` | Maintains extremism, requires probabilities in (0,1) | Inapplicable to signed sentiments in [-1,+1] |
| **Bayesian updating** | Sequential `P(H|E) ∝ P(E|H)P(H)` | Optimal under exchangeability; requires likelihood models | Requires explicit probability models per agent |
| **Trimmed mean** | Discard top/bottom k%, average rest | Robust to outliers | Useful but loses information |
| **Median** | Sort s_i, take middle | Maximum breakdown point (50% corruption tolerance) | Too coarse for continuous signal |

**The forecast combination literature** (Timmermann, 2006, "Forecast Combinations"; Stock & Watson, 2004, "Combination forecasts of output growth") consistently shows that **simple equal-weighted averages often outperform optimally weighted combinations out-of-sample** because weight estimation introduces its own errors. The current scheme adds complexity (confidence weighting + base weights + sell-side correction + correlation discount) that may overfit to assumptions rather than improving accuracy.

**Geometric mean is not applicable here**: The log opinion pool requires probabilities in (0,1). Since this system uses signed sentiment in [-1, +1], the log pool cannot be applied directly without a transformation.

**Bayesian updating** would be the gold standard if you could model `P(s | fundamentals)` for each agent, but that requires a generative model of each agent's behavior — infeasible at this scale.

### Problems

**Problem 1: Confidence as vote weight conflates two things.** An agent may have low confidence because (a) the evidence is genuinely ambiguous or (b) the model is underconfident about a clear signal. These should be treated differently: (a) truly justifies downweighting, (b) is a calibration artifact that should be corrected, not penalized.

**Problem 2: The formula normalizes by `Σ(w_i × c_i)` not `Σ(w_i)`.** This means agents with very low confidence effectively "exit" the consensus, which can lead to the consensus being determined by 1-2 high-confidence agents when others are uncertain. This may be intended behavior, but it means the "9 agents" framing overstates the actual number of contributors.

**Recommendation**: The current formula is defensible. However, track **effective sample size** (ESS = `[Σ w_i]^2 / Σ(w_i^2)` applied to `α_i` weights) to detect when the consensus is driven by only 1-2 agents despite all 9 being present. Add ESS to `VerdictResult` as a diagnostic field.

---

## 3. Sell-Side Bias Correction

### Current Implementation

```python
elif stance.sentiment < 0:
    corrected_c = min(c * Decimal("1.3"), Decimal("1"))
```

Bearish agents get 1.3× confidence boost in vote power. This does not affect the agent's confidence display, only its vote power.

### Empirical Justification Review

The 1.3× multiplier is documented as a "stopgap" calibrating against an observed `BUY confidence = 0.655` vs `SELL confidence = 0.420`. The implied correction factor from raw data is: `0.655 / 0.420 ≈ 1.56`.

**The gap between 1.56 (empirical) and 1.30 (applied) is significant.** By using 1.30 instead of 1.56, the correction is conservative — it partially corrects but leaves a residual bullish tilt.

**Is sell-side optimism bias real?** The academic literature is clear:
- Ramnath, Rock & Shane (2008, *International Journal of Forecasting*): Systematic analyst optimism is well-documented. The ratio of BUY to SELL ratings at major brokerages is typically 5:1 to 8:1.
- Michaely & Womack (1999): Investment banking relationships cause analysts to issue more favorable ratings.
- Hong & Kubik (2003): Career concerns cause analysts to issue optimistic forecasts.

**However, LLM agents are not human sell-side analysts.** The bias observed in the system may be:
1. Inherited from training data biases in the LLMs
2. Prompt design artifacts (optimistic framing in the bullish signal taxonomy)
3. Genuine optimism in the named investment personas (Warren Buffett is historically bullish)
4. Statistically spurious (small sample size)

**Problem**: Applying a fixed 1.3× multiplier without empirical validation on THIS system's actual prediction accuracy is premature. The correction assumes the bias is systematic and constant, but it may vary by: (a) stock type (growth vs value), (b) market regime, (c) individual agent, (d) time.

### Should the Correction Vary by Agent?

Yes. The docstring correctly identifies this as a known limitation. The auditor agent is explicitly designed to be skeptical — its bearish confidence should NOT need boosting. Warren (a Buffett persona) is structurally bullish. Simons (quant) should be closer to neutral.

**Recommendation**:
1. Log `corrected_c` vs `raw_c` per agent and track whether bearish calls are systematically less confident per agent.
2. Replace the global 1.3× with **per-agent calibration multipliers** derived from historical outcome data once 50+ settled predictions exist per agent.
3. Until then, use `1.0×` for the auditor (already skeptical by design) and apply the current 1.3× only to Warren, Soros, Druckenmiller, Dalio.

---

## 4. Correlation Discount

### Current Implementation

```python
_CORRELATION_DISCOUNT = Decimal("0.85")

# Per-provider groups:
# claude: warren, klarman, auditor
# gemini: soros, druckenmiller, dalio
# other: simons, lynch

# Applied: 2nd agent = 0.85x, 3rd agent = 0.72x (0.85^2)
discount = _CORRELATION_DISCOUNT ** count if count > 0 else Decimal("1")
```

### Mathematical Analysis

**This is the Correlated Forecasters Problem.** The standard treatment from Winkler (1981, "Combining Probability Distributions from Dependent Information Sources") is:

For correlated forecasters with correlation matrix `Ω`, the optimal aggregate weight vector is:
```
w* ∝ Ω^(-1) × 1
```

The current approach approximates this with a simple exponential decay, which:
- Reduces the effective weight of the 2nd same-provider agent by 15%
- Reduces the 3rd by 28% (0.85^2 = 0.72)

**Is 0.85 the right factor?** This implies same-provider agents are ~85% as independent as different-provider agents after the first. In practice, the correlation between claude-claude agent pairs vs. claude-gemini pairs depends on:
1. The training data overlap (very high for same model family)
2. The prompt structure (different personas modify base behavior)
3. The information fed (same fundamentals, same data)

A rough analogy: two financial analysts from the same firm given the same briefing materials will produce more correlated forecasts than analysts from competing firms. The correlation penalty of 0.85 may actually be **too lenient** — same-model LLMs given identical inputs may have correlation closer to 0.90-0.95.

**Empirical test possible**: Once you have 50+ predictions where all agents voted, you can compute the empirical Pearson correlation between agent sentiment series and derive proper discount factors.

**A more principled approach**:

```python
# Diversity-weighted aggregation (approximation)
# Discount = (1 - correlation) where correlation estimated from historical data
def diversity_weight(agent_name: str, provider_correlations: dict) -> float:
    # Use empirically measured provider-level sentiment correlation
    ...
```

**Recommendation**: The current structure is correct (apply a discount for correlated sources). The 0.85 coefficient is a reasonable placeholder. Add telemetry to measure actual agent-pair sentiment correlations and recalibrate the discount annually or when 100+ paired observations exist.

---

## 5. Missing Agent Imputation

### Current Implementation

```python
AgentStance(
    name=name,
    sentiment=0.0,
    confidence=Decimal("0.3"),
    key_signals=["IMPUTED_NEUTRAL"],
    ...
)
```

Missing agents are imputed as neutral (sentiment=0.0) with low confidence (0.3).

### Does This Systematically Bias Toward HOLD?

**Yes, with caveats.** The imputed stance pulls the consensus toward zero. Consider:
- 6 real agents all bullish at sentiment=0.6, confidence=0.65
- 3 imputed agents at sentiment=0.0, confidence=0.3

The imputed agents will dampen the consensus, potentially pulling it from BUY territory to ACCUMULATE or WATCHLIST.

**Whether this is correct depends on what "missing" means:**
1. **Agent timed out / error**: Missing does NOT imply neutral. The agent may have had a strong opinion that failed to surface. Neutral imputation is wrong here.
2. **Agent deemed incompetent for this stock type**: Missing IS informative neutral. For example, the Income Analyst not running on a growth stock is appropriate and neutral is the right value.
3. **Agent architecture not yet implemented**: Neutral is a reasonable prior.

**The current code handles case 2 via conditional activation** (Income Analyst, Sector Specialist). But for error/timeout cases (case 1), neutral imputation introduces a systematic dampening that could prevent high-consensus bullish signals from reaching STRONG_BUY.

**Statistical perspective**: Missing-at-random (MAR) vs. missing-not-at-random (MNAR). If agents fail more often on **difficult / ambiguous stocks** (MNAR), then neutral imputation is actually appropriate — the difficulty signals genuine uncertainty. If failures are random (MAR), neutral imputation underweights the remaining agents' signal strength.

**Alternatives**:
1. **Mean imputation**: Impute with the current consensus (iterative). Complex but reduces dampening.
2. **Exclusion with ESS penalty**: Don't impute, but multiply the final confidence by `n_present / n_expected`. This penalizes missing data without pulling sentiment to zero.
3. **Provider-level imputation**: If warren is missing, impute from klarman's stance (same provider, likely correlated). Better than neutral.

**Recommendation**: Keep neutral imputation as the default, but add a flag `VerdictResult.agents_missing: int` so callers can see how many agents were imputed. For the synthesis verdict, apply an additional confidence penalty when `agents_missing >= 3`:

```python
if imputed_count >= 3:
    final_confidence *= Decimal("0.85")  # Penalize for sparse attendance
```

---

## 6. Verdict Thresholds

### Current 8-Level System

```
sentiment >= 0.55 AND confidence >= 0.70 → STRONG_BUY
sentiment >= 0.30 AND confidence >= 0.50 → BUY
sentiment >= 0.15 AND confidence >= 0.40 → ACCUMULATE
sentiment >= 0.10 AND confidence < 0.40  → WATCHLIST
sentiment >= -0.10                        → HOLD
sentiment >= -0.30                        → REDUCE
sentiment >= -0.50                        → SELL
sentiment < -0.50                         → AVOID
```

### Mathematical Analysis

**The dual-gate system (sentiment AND confidence)** creates non-convex decision regions. A stock with sentiment=0.58 and confidence=0.65 would be classified as **BUY** (fails strong_buy_confidence gate), while sentiment=0.55 and confidence=0.70 is STRONG_BUY. The gap between these two points is 0.05 in confidence but they produce different outcomes. This is correct behavior for high-conviction gating but creates unexpected results near boundaries.

**Single composite score alternative:**
```
composite = sentiment × confidence
```
This collapses the 2D gate to a 1D scale. However, this conflates two orthogonal concepts:
- `sentiment = 0.9, confidence = 0.3` → composite = 0.27 (high conviction but uncertain analyst)
- `sentiment = 0.3, confidence = 0.9` → composite = 0.27 (moderate conviction, very confident)

These should arguably produce different verdicts. The dual-gate system correctly distinguishes them. **The current design is better than a single composite for this reason.** ✓

**Are the thresholds well-calibrated?**
- STRONG_BUY requires sentiment >= 0.55 (consistently bullish with 5+ signals weighted toward 1.5x on average) AND confidence >= 0.70. For 9 agents, reaching consensus sentiment of 0.55+ requires approximately 7-8 agents to be clearly bullish. This seems appropriate for "strong consensus."
- BUY at sentiment >= 0.30 requires approximately 65% of weighted signal mass to be bullish. Moderate but clear positive.
- WATCHLIST captures the region where sentiment is weakly positive (0.10-0.15) but confidence is below the ACCUMULATE threshold. This is the "interesting but not ready" zone.
- HOLD spans [-0.10, +0.10]: a 20-point wide region. This is appropriately wide — genuine neutrality should produce HOLD, not WATCHLIST or REDUCE.

**Potential calibration issue**: The WATCHLIST gate requires `sentiment >= 0.10 AND confidence < 0.40`. This means a highly uncertain bullish signal goes to WATCHLIST, which is correct. But a highly uncertain bearish signal (sentiment = -0.15, confidence = 0.20) would fall through to **REDUCE** (sentiment >= -0.30), not to WATCHLIST. Arguably, low-confidence bearish should also be a watchlist/hold event. Consider:

```python
# Add: low confidence + bearish → WATCHLIST (uncertain, don't act on REDUCE)
if sent >= Decimal("-0.30") and confidence < Decimal("0.35"):
    return Verdict.WATCHLIST, float(abs(sent - Decimal("-0.10")))
```

**Decision boundary shape**: The current system uses rectangular (AND-gated) boundaries. This means a slight dip in either sentiment or confidence can change the verdict. A **soft boundary** using a composite score would be smoother:

```python
composite = float(sent) * float(confidence)
# STRONG_BUY: composite >= 0.385 (= 0.55 × 0.70)
# BUY: composite >= 0.15 (= 0.30 × 0.50)
```

However, rectangular gates are more interpretable for debugging and are the standard in practitioner frameworks (Morningstar's moat + uncertainty matrix uses this exact pattern).

**Recommendation**: The 8-level system is appropriate for a practitioner tool. The thresholds themselves are not unreasonable, but they have not been back-tested against outcomes. Add `verdict_calibration` telemetry: track `(predicted_verdict, actual_6m_return)` pairs and compute whether STRONG_BUY stocks actually outperform BUY stocks significantly. This will allow empirical threshold tuning after 100+ predictions.

---

## 7. Regime Adjustment

### Current Implementation

```python
_REGIME_THRESHOLD_ADJ = {
    "fear": {
        "buy_sentiment": Decimal("0.35"),       # raised from 0.30
        "strong_buy_confidence": Decimal("0.75"), # raised from 0.70
    },
    "extreme_fear": {
        "buy_sentiment": Decimal("0.40"),
        "strong_buy_confidence": Decimal("0.80"),
    },
}
```

In fear regimes, the system **raises** buy thresholds, making it **harder** to get a BUY verdict.

### Contrarian vs. Momentum Perspective

This is one of the most contested design decisions in quantitative finance.

**The system's implicit assumption (momentum/risk-management)**: Fear signals elevated risk; require more conviction before committing capital. This aligns with **risk parity** approaches (Dalio's All-Weather) where tail risk is priced in.

**The contrarian counter-argument (Buffett, Templeton, Marks)**: "Be fearful when others are greedy, and greedy when others are fearful." Fear regimes are precisely when quality assets are available at maximum discount. Raising the BUY threshold in fear is equivalent to saying "buy only at the highest conviction when assets are cheapest" — this is actually consistent with contrarianism! You're not lowering the bar; you're ensuring that when you buy at the maximum discounted price, you're not doing so on weak conviction.

**Academic evidence**:
- DeBondt & Thaler (1985, *Journal of Finance*): Extreme losers outperform extreme winners over 3-5 years — consistent with contrarian buying in fear.
- Baker & Wurgler (2006, *Journal of Finance*): Sentiment-based investment strategies: low sentiment predicts high subsequent returns, but with high variance.
- Stambaugh, Yu & Yuan (2012): Effect of investor sentiment on cross-sectional stock returns — sentiment affects mispricing.

**The correct resolution**: The regime adjustment should be applied differently based on the **investment thesis**:

| Position Type | Fear Regime Response | Rationale |
|--------------|---------------------|-----------|
| Tactical/momentum | RAISE threshold | Fear signals trend reversal risk; don't buy into falling knives |
| Value/contrarian | LOWER or KEEP threshold | Fear = wider margin of safety |
| Permanent/quality | KEEP or slightly raise | Long-term; short-term fear is noise |

The current code has placeholder `_TYPE_REGIME_OVERRIDES` with empty entries for `permanent` but doesn't explicitly lower thresholds for value stocks in fear.

**Recommendation**:
1. Document that the regime logic is a **risk filter, not a contrarian signal**. It prevents buying into momentum-driven declines with low conviction; it does not prevent buying high-quality stocks at depressed prices (the agents' fundamentals analysis handles that via sentiment).
2. For `permanent` position types in `fear` regime, explicitly KEEP base thresholds (don't raise them):
   ```python
   ("permanent", "fear"): {"buy_sentiment": Decimal("0.30")},  # Keep base, don't raise
   ```
3. Consider adding `regime_override_reason` to `VerdictResult` so users understand why a STRONG_BUY degraded to BUY.

---

## 8. Debate System

### Current Design

- **Trigger**: `< 75%` same-direction sentiment among primary agents
- **Rules**: Cannot change direction; can adjust confidence and signals
- **Effect**: Updates responses in place; revised responses fed to synthesis

### Is 75% the Right Threshold?

**The 75% threshold for consensus** is equivalent to a **supermajority rule**. In voting theory (Black's median voter theorem, Condorcet jury theorem), requiring supermajority:
- Reduces false positives (prevents borderline cases from being decided on slim majorities)
- Increases false negatives (can fail to act on genuine opportunities when one contrarian agent holds out)

**Condorcet Jury Theorem** (Condorcet, 1785): If each juror is more likely than not to be correct, majority voting is more accurate than any individual, and accuracy increases with group size. For `p_i > 0.5` per agent, the probability of correct group verdict asymptotes to 1 as n→∞.

The extension to **weighted voting** (Nitzan & Paroush, 1982): The optimal decision rule is to weight each voter proportional to `log(p_i / (1-p_i))` — which is exactly what the confidence-weighted consensus approximates.

**At 75% threshold**: With 6 primary agents (Warren, Auditor, Klarman, Soros, Druckenmiller, Dalio), 75% requires at least 4.5 → 5 of 6 to agree. This means **debate triggers when 2+ primary agents dissent**. This is a relatively aggressive trigger.

**Does debate improve accuracy?**
- The docstring references "~13% accuracy improvement (AI Hedge Fund)" which is anecdotal.
- In the academic group decision literature, **structured debate** (having dissenters articulate their position) does improve group accuracy through information aggregation (Sunstein & Hastie, 2015, "Wiser: Getting Beyond Groupthink to Make Groups Smarter").
- However, **with LLMs the direction-lock rule is problematic**: forcing an LLM to maintain its original direction while updating confidence may cause incoherent responses (defending a thesis it no longer believes but is forbidden from changing).

**The direction-lock rule**: "You CANNOT change your overall direction (bullish/bearish/neutral)." This is designed to prevent herding — if all agents are allowed to fully revise, they may converge to a single view (the most persuasively stated position), eliminating diversity. The direction-lock preserves diversity. This is **the correct design for adversarial debate**. ✓

However: If an agent was marginally bullish (sentiment=0.12) and sees strong bearish arguments from peers, locking its direction means it can only reduce confidence (from 0.65 to 0.55) rather than shifting stance. This keeps a slightly-bullish agent voting slightly bullish even though it now believes the argument is stronger the other way. This is a **systematic tilt toward original positions**.

**Recommendation**:
1. Keep the 75% threshold. It's slightly aggressive (triggers debate often) but this is appropriate for high-stakes investment decisions.
2. Relax the direction-lock to allow ±1 level shifts: bullish may become neutral, but not bearish. This allows edge cases to update without full herding.
3. Track `debate_count_triggered` and `debate_sentiment_shift` (average change in consensus before/after debate) as telemetry. If average shift is < 0.02, debate is adding latency without improving outcomes.

---

## 9. Auditor Veto

### Current Implementation

```python
if auditor.sentiment < -0.3 and auditor.confidence >= Decimal("0.6"):
    auditor_override = True
    # Effect: caps verdict at WATCHLIST if sentiment > 0.2, else AVOID
```

### Mathematical Analysis

**What this means**: The auditor can override the consensus of 8 other agents when it is (a) bearish enough and (b) confident enough. This is a **structural minority veto** — a single agent with special powers.

**Threshold analysis**:
- `sentiment < -0.3`: Requires the auditor to have more bearish signal mass than 65% of total signal mass. This is not easily triggered — the auditor must clearly flag significant risks.
- `confidence >= 0.6`: Moderate confidence. The auditor doesn't need to be certain, just confident. This asymmetry (lower bar for triggering veto than for issuing STRONG_BUY) reflects the precautionary principle: **it's easier to block than to approve**.

**Is this the right design?** Yes, with reservations:
- Financial risk management consistently shows that **asymmetric loss functions** (losses from undetected risk > gains from missed opportunity) justify asymmetric decision rules.
- Nassim Taleb's work on tail risk: rare, severe downside events are systematically underweighted by consensus forecasters. A skeptical auditor with veto power operationalizes this insight.
- The 0.6 confidence threshold for veto vs. 0.7 for STRONG_BUY is appropriate asymmetry.

**Potential problem**: The auditor sentiment and confidence are computed using the same `_compute_sentiment()` function applied to the auditor's signals. Since the auditor's persona explicitly focuses on **risks** (negative signals), the auditor will systematically produce more negative signal tags than other agents. This means:
- The auditor's `sentiment` will be lower on average than other agents'
- The veto condition (`sentiment < -0.3`) will trigger more often for auditor than it would for other agents at the same fundamental quality level

This is **intended behavior** (the auditor is designed to be skeptical), but it means the veto effectively fires even for moderately risky stocks. The threshold `< -0.3` with `confidence >= 0.6` may be too easily triggered once the system matures.

**Recommendation**: Add a **counter-veto check**: the auditor veto should also require that at least 2 of the remaining agents would not independently veto. This prevents the auditor from blocking a stock that 8/9 agents are highly bullish about based on edge-case risk concerns:

```python
# Only apply auditor override if the concern is not isolated
non_auditor_bearish = sum(1 for s in stances if s.name != "auditor" and s.sentiment < -0.1)
if non_auditor_bearish < 2:
    # Auditor alone is bearish — soften the veto (WATCHLIST, not AVOID)
    # Unless auditor confidence is very high (>= 0.8)
    if auditor.confidence < Decimal("0.8"):
        auditor_override = False  # Downgrade to flagging only
```

---

## 10. Confidence Calibration

### Current Design

```python
if calibrator and hasattr(calibrator, "is_calibrated") and calibrator.is_calibrated(stance.name):
    corrected_c = calibrator.calibrate(stance.name, c)
elif stance.sentiment < 0:
    corrected_c = min(c * Decimal("1.3"), Decimal("1"))
```

Isotonic regression calibration is used when an agent has "enough settled predictions (100+)".

### Mathematical Analysis

**Isotonic Regression** (Zadrozny & Elkan, 2002): A non-parametric, monotone-constrained calibration method. For confidence calibration:
- Input: raw model confidence scores `p̂ ∈ [0,1]`
- Output: calibrated probabilities `p_cal ∈ [0,1]`
- Constraint: calibrated values are monotone (higher raw confidence → higher calibrated confidence)
- Algorithm: Pool Adjacent Violators (PAV)

**Comparison of calibration methods:**

| Method | Parameters | Sample Requirement | Assumptions | Best For |
|--------|-----------|-------------------|-------------|----------|
| **Isotonic regression** | None (non-parametric) | 100-500+ samples | Monotone relationship | Flexible, works with irregularly spaced scores |
| **Platt scaling** | 2 (logistic: a, b) | 50-100 samples | Sigmoid relationship | Fast, interpretable, good when overconfidence is systematic |
| **Temperature scaling** | 1 (T) | 50+ samples | Divides logits by T | Excellent for LLM outputs; preserves accuracy |
| **Beta calibration** (Kull 2017) | 3 (a, b, c) | 100+ samples | Beta distribution | Best for non-sigmoid miscalibration curves |
| **Histogram binning** | k bins | k × 30 samples | None (non-parametric) | Simple, interpretable, requires many samples |

**For LLM confidence outputs specifically**: Temperature scaling is the best-studied method for neural network outputs (Guo et al., 2017, "On Calibration of Modern Neural Networks"). Since LLM agents produce confidence scores in [0,1] that are inherently over- or under-confident depending on prompt design, temperature scaling is the most principled choice.

**Temperature scaling**: `p_cal = σ(logit(p) / T)` where `T > 1` reduces overconfidence, `T < 1` increases it. Requires one parameter and ~50 samples.

**Required sample sizes for reliable calibration:**
- Isotonic regression with PAV: typically needs 500+ samples for stable calibration (Niculescu-Mizil & Caruana, 2005)
- At 100 settled predictions per agent, calibration will be unstable with high variance
- The 100+ threshold in the code is likely insufficient — recommend 300+

**Brier Score** for tracking calibration quality:
```
BS = (1/N) × Σ(p_i - o_i)^2
```
where `o_i ∈ {0, 1}` is the actual outcome (stock outperformed benchmark within 6 months). Lower is better. A perfect predictor scores 0; always predicting 0.5 scores 0.25. Track Brier score per agent.

**Brier Score Decomposition** (Murphy, 1973):
```
BS = Reliability + Resolution - Uncertainty
```
- **Reliability** (calibration error): How well probabilities match frequencies
- **Resolution**: How much the predictions vary from the base rate
- **Uncertainty**: Base rate entropy (fixed, not agent-controlled)

Tracking these separately identifies whether an agent is poorly calibrated (reliability) vs. uninformative (resolution).

**Recommendation**:
1. Replace isotonic regression target with **temperature scaling** as the primary calibration method. Simpler, faster, and better suited to LLM confidence scores.
2. Require 300+ settled predictions before applying calibration (not 100+).
3. Add Brier score reporting to the learning/calibration module, decomposed into reliability and resolution components.
4. Until calibration is active, keep the 1.3× sell-side correction but document it as a "prior correction" not a calibration substitute.

---

## 11. Overall Aggregation Architecture

### Is the System Well-Designed?

The synthesis pipeline is structured as:
```
agent_signals → imputation → correlation discount → confidence weighting → sell-side correction → calibration → threshold gating → auditor veto → verdict
```

**This is a correct and principled pipeline.** Each stage addresses a documented problem:
- Imputation: handles sparse attendance
- Correlation discount: handles information overlap
- Confidence weighting: allows experts to signal certainty
- Sell-side correction: corrects systematic LLM optimism bias
- Calibration: aligns stated confidence with actual accuracy
- Threshold gating: maps continuous score to discrete action
- Auditor veto: implements precautionary principle

**The main architectural risk** is **compounding corrections**: if sell-side correction AND calibration AND imputation all fire simultaneously, the resulting sentiment may be far from what any single mechanism intended. A miscalibrated correction at one stage amplifies through subsequent stages.

**Recommendation**: Add a `VerdictResult.correction_log: list[str]` field that records each correction applied and its magnitude. This allows debugging and detecting when compounding corrections are distorting the final result.

---

## Summary of Recommendations

| Issue | Current State | Recommendation | Priority |
|-------|--------------|----------------|----------|
| Sentiment formula double-penalty | `sentiment × evidence_factor` | Separate: evidence_factor → confidence, not sentiment | Medium |
| Sell-side correction magnitude | 1.3× (empirical: 1.56×) | Per-agent multipliers from historical data; global stop at 1.56×. Auditor: 1.0× | High |
| Correlation discount coefficient | 0.85 (arbitrary) | Measure empirical agent-pair correlations; recalibrate | Low (future) |
| Missing agent imputation | Neutral (sentiment=0, conf=0.3) | Add agents_missing field; confidence penalty when >= 3 imputed | Medium |
| Verdict thresholds | Dual-gate rectangular | Add soft gate for low-confidence bearish → WATCHLIST | Low |
| Regime thresholds | Fear raises buy threshold | Explicitly keep base thresholds for permanent/value positions | Medium |
| Debate direction-lock | Cannot change direction | Allow ±1 level (bullish → neutral allowed) | Low |
| Auditor veto isolation | Single veto without check | Add counter-veto: require 2+ other agents also concerned | Medium |
| Calibration method | Isotonic regression, 100+ | Temperature scaling, 300+ samples; add Brier score tracking | High |
| Compounding corrections | No logging | Add correction_log to VerdictResult | Medium |
| Effective sample size | Not tracked | Add ESS to VerdictResult as diagnostic | Low |

---

## Literature References

- Bates & Granger (1969). "The Combination of Forecasts." *Operational Research Quarterly*, 20(4).
- Black's Median Voter Theorem (1948). *Journal of Political Economy*.
- Condorcet (1785). *Essai sur l'Application de l'Analyse à la Pluralité des Voix*. Jury Theorem.
- DeBondt & Thaler (1985). "Does the Stock Market Overreact?" *Journal of Finance*, 40(3).
- Guo, Pleiss, Sun, Weinberger (2017). "On Calibration of Modern Neural Networks." *ICML 2017*.
- Hong & Kubik (2003). "Analyzing the Analysts: Career Concerns and Biased Earnings Forecasts." *Journal of Finance*, 58(1).
- Kull, Silva Filho, Flach (2017). "Beta Calibration." *AISTATS 2017*.
- Loughran & McDonald (2011). "When is a Liability not a Liability?" *Journal of Finance*, 66(1).
- Michaely & Womack (1999). "Conflict of Interest and the Credibility of Underwriter Analyst Recommendations." *Review of Financial Studies*, 12(4).
- Murphy (1973). "A New Vector Partition of the Probability Score." *Journal of Applied Meteorology*.
- Niculescu-Mizil & Caruana (2005). "Predicting Good Probabilities with Supervised Learning." *ICML 2005*.
- Nitzan & Paroush (1982). "Optimal Decision Rules in Uncertain Dichotomous Choice Situations." *International Economic Review*.
- Ramnath, Rock & Shane (2008). "The Financial Analyst Forecasting Literature: A Taxonomy with Suggestions for Future Research." *International Journal of Forecasting*, 24(1).
- Stone (1961). "The Opinion Pool." *Annals of Mathematical Statistics*, 32(4).
- Sunstein & Hastie (2015). *Wiser: Getting Beyond Groupthink to Make Groups Smarter*. Harvard Business Review Press.
- Taleb (2007). *The Black Swan*. Random House.
- Timmermann (2006). "Forecast Combinations." In *Handbook of Economic Forecasting*, Elsevier.
- Winkler (1968). "The Consensus of Subjective Probability Distributions." *Management Science*, 15(2).
- Winkler (1981). "Combining Probability Distributions from Dependent Information Sources." *Management Science*, 27(4).
- Zadrozny & Elkan (2002). "Transforming Classifier Scores into Accurate Multiclass Probability Estimates." *KDD 2002*.

---

*End of deep review — synthesis mathematics.*
