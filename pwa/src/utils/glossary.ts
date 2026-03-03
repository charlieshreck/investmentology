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
  "piotroski f-score": "Nine-point test for financial strength. Score of 7-9 is strong, 0-3 is weak.",
  "earnings yield": "How much profit per dollar you pay for the stock. Higher is cheaper — like a better interest rate.",
  "composite score": "Our combined ranking blending value, quality, and momentum into one number.",
  "combined rank": "Overall ranking among all screened stocks. Lower number means better opportunity.",
  roic: "Return on invested capital — how efficiently the company turns investment into profit.",
  "magic formula": "Joel Greenblatt's strategy: buy good companies (high ROIC) at cheap prices (high earnings yield).",

  // Risk & quality
  "market cap": "Total value of all company shares. Large cap (>$10B) is safer, small cap (<$2B) is riskier.",
  moat: "Competitive advantage that protects profits from competitors — like a castle moat defends a fortress.",
  "dividend yield": "Annual dividend payment as a percentage of stock price. Like an annual interest payment.",
  "beta": "How much a stock moves vs. the market. Beta > 1 means more volatile, < 1 means calmer.",

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
};

/** Look up a term in the glossary (case-insensitive). */
export function lookupTerm(term: string): string | null {
  return TERM_GLOSSARY[term.toLowerCase()] ?? null;
}
