/**
 * Shared vocabulary for the investment platform.
 * Single source of truth for plain-English labels and explanations.
 */

// Pre-filter rule explanations (from Pipeline)
export const PRE_FILTER_EXPLANATIONS: Record<string, string> = {
  altman_z_distress: "Shows signs of potential bankruptcy",
  piotroski_catastrophic: "Fails nearly every financial health test",
  triple_negative: "Losing money and shrinking at the same time",
  extreme_pe_no_growth: "Stock price is extremely expensive with no growth to back it up",
  losing_and_shrinking: "Unprofitable and getting smaller",
  debt_implosion: "Debts are almost equal to everything the company owns",
};

// Screener names + descriptions
export const SCREENER_NAMES: Record<string, { label: string; description: string }> = {
  financial_health_screener: {
    label: "Financial Health",
    description: "Can this company survive tough times?",
  },
  valuation_screener: {
    label: "Valuation",
    description: "Does the stock price make sense?",
  },
  growth_momentum_screener: {
    label: "Growth & Momentum",
    description: "Are things heading in the right direction?",
  },
  quality_position_screener: {
    label: "Quality & Position",
    description: "Does this company have a competitive edge?",
  },
};

// Financial term glossary — short explanations (~20 words each)
export const TERM_GLOSSARY: Record<string, string> = {
  // Screening metrics
  "altman z-score": "Mathematical formula predicting bankruptcy risk. Above 3.0 is safe, below 1.8 is distress zone.",
  "altman z": "Mathematical formula predicting bankruptcy risk. Above 3.0 is safe, below 1.8 is distress zone.",
  "z-score": "Mathematical formula predicting bankruptcy risk. Above 3.0 is safe, below 1.8 is distress zone.",
  "piotroski f-score": "Nine-point test for financial strength. Score of 7-9 is strong, 0-3 is weak.",
  "piotroski": "Nine-point test for financial strength. Score of 7-9 is strong, 0-3 is weak.",
  "f-score": "Piotroski's nine-point test for financial strength. Score of 7-9 is strong, 0-3 is weak.",
  "earnings yield": "How much profit per dollar you pay for the stock. Higher is cheaper — like a better interest rate.",
  "composite score": "Our combined ranking blending value, quality, and momentum into one number.",
  "combined rank": "Overall ranking among all screened stocks. Lower number means better opportunity.",
  roic: "Return on invested capital — how efficiently the company turns investment into profit.",
  "magic formula": "Joel Greenblatt's strategy: buy good companies (high ROIC) at cheap prices (high earnings yield).",

  // Risk & quality
  "market cap": "Total value of all company shares. Large cap (>$10B) is safer, small cap (<$2B) is riskier.",
  moat: "Competitive advantage that protects profits from competitors — like a castle moat defends a fortress.",
  "dividend yield": "Annual dividend payment as a percentage of stock price. Like an annual interest payment.",
  beta: "How much a stock moves vs. the market. Beta > 1 means more volatile, < 1 means calmer.",

  // Verdict & signals
  consensus: "The combined opinion of all investment agents, weighted by their expertise and confidence.",
  conviction: "How strongly the agents believe in their recommendation. Higher means more certain.",
  "thesis health": "Whether the original reason for buying still holds. INTACT is good, BROKEN means sell.",
  "success probability": "Estimated chance this recommendation will be profitable based on agent analysis.",

  // Agent concepts
  "signal tag": "A specific data point or pattern an agent identified (e.g. 'strong earnings growth').",
  "contrarian signal": "A signal where only one agent disagrees with the majority — worth paying attention to.",
  "consensus tier": "Classification of agent agreement: High Conviction (most agree), Mixed, or Contrarian.",

  // Portfolio concepts
  "position type": "Classification of why you hold a stock: core (long-term), tactical (short-term), speculative.",
  "cost basis": "Average price you paid per share. Used to calculate profit/loss.",
  "unrealized p&l": "Profit or loss on positions you still hold — only 'real' when you sell.",
  "realized p&l": "Actual profit or loss from closed positions.",

  // Performance metrics
  "sharpe ratio": "Risk-adjusted return. Above 1.0 is good, above 2.0 is excellent. Shows return per unit of risk taken.",
  "sharpe": "Risk-adjusted return. Above 1.0 is good, above 2.0 is excellent. Shows return per unit of risk taken.",
  "sortino ratio": "Like Sharpe but only penalises downside risk. Higher is better — ignores upside volatility.",
  "sortino": "Like Sharpe but only penalises downside risk. Higher is better — ignores upside volatility.",
  alpha: "Return above what the market delivered. Positive alpha means beating the benchmark.",
  "max drawdown": "Largest peak-to-trough portfolio drop. The worst loss you would have experienced.",
  "win rate": "Percentage of trades that were profitable. Above 50% is decent, but size of wins matters more.",
  "disposition ratio": "Ratio of how long you hold winners vs losers. Above 1.0 means cutting losers faster — good.",

  // Valuation
  "p/e ratio": "Price-to-earnings. How much you pay per $1 of profit. Lower is cheaper — compare within sector.",
  "p/e": "Price-to-earnings ratio. How much you pay per $1 of profit. Lower is cheaper — compare within sector.",
  "pe ratio": "Price-to-earnings. How much you pay per $1 of profit. Lower is cheaper — compare within sector.",
  "forward p/e": "P/E using next year's estimated earnings. Lower than trailing P/E suggests growth ahead.",
  "trailing p/e": "P/E using last 12 months of actual earnings. The backwards-looking valuation measure.",
  "p/b": "Price-to-book. Stock price vs company's net assets. Below 1.0 means paying less than asset value.",
  "p/s": "Price-to-sales. Stock price relative to revenue. Useful for unprofitable growth companies.",
  "price to book": "Stock price vs company's net assets. Below 1.0 means paying less than asset value.",
  "price to sales": "Stock price relative to revenue. Useful for unprofitable growth companies.",
  "enterprise value": "Total company value including debt minus cash. More accurate than market cap for comparisons.",
  "ev/ebitda": "Enterprise value relative to operating cash earnings. Lower means cheaper — cross-sector comparison.",
  "price to earnings": "How much you pay per $1 of profit. Lower is cheaper — compare within sector.",

  // Agent system
  "consensus score": "Agreement among our AI analysts, from -1.0 (all bearish) to +1.0 (all bullish).",
  "munger override": "Adversarial check (inspired by Charlie Munger) found critical flaws — recommendation downgraded.",
  "auditor override": "Risk analyst flagged high-confidence concerns, capping the recommendation.",
  "stability score": "How consistent the verdict has been across recent analyses. STABLE means no recent flips.",
  "brier score": "Prediction accuracy metric. 0.0 is perfect, 0.25 is coin-flip. Lower is better.",

  // Company fundamentals
  "operating income": "Profit from core business operations, before interest and taxes.",
  "net income": "Bottom-line profit after all expenses, taxes, and interest.",
  revenue: "Total sales before any costs are subtracted. The 'top line' number.",
  "free cash flow": "Cash left after running the business and investing. Available to shareholders.",
  "payout ratio": "Percentage of earnings paid as dividends. Below 60% is sustainable, above 80% is risky.",
  "gross margin": "Revenue minus cost of goods, as a percentage. Shows pricing power and efficiency.",
  "operating margin": "Operating income as a percentage of revenue. Higher means more efficient operations.",
  "net margin": "Net income as a percentage of revenue. The bottom-line profitability measure.",
  "debt to equity": "Total debt relative to shareholder equity. Above 2.0 is heavily leveraged.",
  "current ratio": "Current assets divided by current liabilities. Above 1.0 means can pay short-term bills.",

  // Abbreviations & shorthand (appear in agent prose)
  fcf: "Free cash flow — cash left after running the business and investing. Available to shareholders.",
  eps: "Earnings per share — net income divided by shares outstanding. The per-share profit measure.",
  ebitda: "Earnings before interest, taxes, depreciation, amortisation. A proxy for operating cash flow.",
  ebit: "Earnings before interest and taxes. Core operating profit before financing costs.",
  dcf: "Discounted cash flow — valuation method that estimates what future cash flows are worth today.",
  ttm: "Trailing twelve months — the most recent 12-month period of financial data.",
  yoy: "Year over year — comparison to the same period last year.",
  cagr: "Compound annual growth rate — smoothed annualised growth rate over a period.",
  "d/e": "Debt-to-equity ratio. Total debt relative to shareholder equity. Above 2.0 is heavily leveraged.",
  roe: "Return on equity — net income as a percentage of shareholder equity.",
  roa: "Return on assets — net income as a percentage of total assets.",

  // Patterns that appear in agent analysis
  "8q streak": "Eight consecutive quarters (2 years) of earnings growth — a strong momentum signal.",
  "margin of safety": "Buying below estimated value to cushion against errors. Core Buffett/Graham concept.",
  "circle of competence": "Investing only in businesses you truly understand. Buffett's core risk management idea.",
  "intrinsic value": "Estimated true worth of a company based on fundamentals, independent of market price.",
  "book value": "Company's net assets (total assets minus total liabilities). What shareholders would get in liquidation.",
  "fair value": "Estimated price a stock should trade at based on fundamentals and growth prospects.",
  "buy and hold": "Long-term strategy — buy quality companies and hold through market fluctuations.",
  "mean reversion": "The tendency for prices to return to their long-term average over time.",
  "risk-adjusted": "Returns measured relative to the amount of risk taken. Higher is better for the same risk.",
  "terminal value": "Estimated value of a business beyond the forecast period in a DCF model.",
  "weighted average cost of capital": "Blended cost of debt and equity financing. Used as DCF discount rate.",
  wacc: "Weighted average cost of capital — blended cost of debt and equity. Used as DCF discount rate.",
  "kelly criterion": "Mathematical formula for optimal position sizing based on edge and odds.",
};

/** Look up a term in the glossary (case-insensitive). */
export function lookupTerm(term: string): string | null {
  return TERM_GLOSSARY[term.toLowerCase()] ?? null;
}

/**
 * Build a regex that matches any glossary term in text.
 * Sorted longest-first so "piotroski f-score" matches before "piotroski".
 * Cached on first call.
 */
let _termRegex: RegExp | null = null;

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function getTermRegex(): RegExp {
  if (_termRegex) return _termRegex;
  const keys = Object.keys(TERM_GLOSSARY).sort((a, b) => b.length - a.length);
  const pattern = keys.map(escapeRegex).join("|");
  _termRegex = new RegExp(`\\b(${pattern})\\b`, "gi");
  return _termRegex;
}

export interface GlossaryMatch {
  term: string;
  definition: string;
  index: number;
  length: number;
}

/**
 * Find all glossary terms in a text string.
 * Returns only the first occurrence of each term (case-insensitive).
 */
export function findGlossaryTerms(text: string): GlossaryMatch[] {
  const regex = getTermRegex();
  regex.lastIndex = 0;
  const matches: GlossaryMatch[] = [];
  const seen = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = regex.exec(text)) !== null) {
    const key = m[0].toLowerCase();
    if (seen.has(key)) continue;
    const def = TERM_GLOSSARY[key];
    if (!def) continue;
    seen.add(key);
    matches.push({ term: m[0], definition: def, index: m.index, length: m[0].length });
  }
  return matches.sort((a, b) => a.index - b.index);
}
