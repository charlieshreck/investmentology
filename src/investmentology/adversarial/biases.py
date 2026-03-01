from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BiasCheck:
    name: str
    description: str
    check_question: str  # Question to ask about the investment
    red_flag_keywords: list[str]  # Keywords in reasoning that suggest this bias


@dataclass
class BiasResult:
    bias_name: str
    is_flagged: bool
    detail: str


# Munger's cognitive biases relevant to investing
COGNITIVE_BIASES: list[BiasCheck] = [
    BiasCheck(
        name="Confirmation Bias",
        description="Seeking only data that confirms our thesis while ignoring contradictory evidence.",
        check_question="Are we only looking at data that confirms our thesis?",
        red_flag_keywords=["confirms", "as expected", "proves our thesis", "validates"],
    ),
    BiasCheck(
        name="Anchoring",
        description="Over-relying on the first piece of information encountered (often a price or metric).",
        check_question="Are we anchored to a specific price or metric?",
        red_flag_keywords=["was trading at", "used to be", "historical high", "52-week", "previous price"],
    ),
    BiasCheck(
        name="Sunk Cost Fallacy",
        description="Continuing an investment because of what has already been invested rather than future prospects.",
        check_question="Are we holding because of what we've already invested?",
        red_flag_keywords=["already invested", "can't sell now", "too late to exit", "average down"],
    ),
    BiasCheck(
        name="Availability Bias",
        description="Overweighting recent or vivid events in decision-making.",
        check_question="Are we overweighting recent or vivid events?",
        red_flag_keywords=["just happened", "recently", "in the news", "everyone is talking about", "viral"],
    ),
    BiasCheck(
        name="Social Proof",
        description="Following the crowd or buying because others are buying.",
        check_question="Are we buying because others are?",
        red_flag_keywords=["everyone is buying", "popular pick", "trending", "hedge funds are", "Buffett bought"],
    ),
    BiasCheck(
        name="Overconfidence",
        description="Excessive certainty in our analysis or predictions.",
        check_question="Are we overestimating our ability to predict outcomes?",
        red_flag_keywords=["guaranteed", "certain", "no way it fails", "can't lose", "slam dunk", "sure thing"],
    ),
    BiasCheck(
        name="Loss Aversion",
        description="Feeling losses roughly twice as strongly as equivalent gains, leading to poor risk management.",
        check_question="Are we avoiding a rational action because we fear recognizing a loss?",
        red_flag_keywords=["can't take the loss", "will recover", "just need to wait", "break even"],
    ),
    BiasCheck(
        name="Recency Bias",
        description="Overweighting recent performance and extrapolating it into the future.",
        check_question="Are we extrapolating recent trends indefinitely?",
        red_flag_keywords=["last quarter", "recent growth", "momentum will continue", "trend will persist"],
    ),
    BiasCheck(
        name="Survivorship Bias",
        description="Focusing on winners while ignoring the many losers, skewing our analysis.",
        check_question="Are we only looking at successful companies in this sector?",
        red_flag_keywords=["like Amazon", "the next Apple", "just like Netflix", "following the winners"],
    ),
    BiasCheck(
        name="Authority Bias",
        description="Overweighting opinions of perceived authority figures without independent analysis.",
        check_question="Are we deferring to authority rather than doing our own analysis?",
        red_flag_keywords=["analyst says", "expert predicts", "guru recommends", "according to the CEO"],
    ),
    BiasCheck(
        name="Narrative Fallacy",
        description="Constructing compelling stories around data that may be coincidental.",
        check_question="Are we building a story that sounds good but may not be supported by data?",
        red_flag_keywords=["the story is", "narrative", "compelling thesis", "the vision", "the dream"],
    ),
    BiasCheck(
        name="Endowment Effect",
        description="Overvaluing what we already own simply because we own it.",
        check_question="Would we buy this stock at today's price if we didn't already own it?",
        red_flag_keywords=["our position", "we own", "our holding", "in our portfolio"],
    ),
    BiasCheck(
        name="Bandwagon Effect",
        description="Adopting beliefs because many other people hold them.",
        check_question="Is this idea popular simply because many people believe it?",
        red_flag_keywords=["consensus", "everyone agrees", "widely held view", "market expects"],
    ),
    BiasCheck(
        name="Halo Effect",
        description="Letting a positive impression in one area influence judgment in other areas.",
        check_question="Are we letting a strong brand or charismatic CEO blind us to business weaknesses?",
        red_flag_keywords=["great CEO", "amazing brand", "visionary leader", "best in class management"],
    ),
    BiasCheck(
        name="Hindsight Bias",
        description="Believing after the fact that an event was predictable.",
        check_question="Are we using hindsight to justify our prediction as if it was obvious?",
        red_flag_keywords=["obvious in retrospect", "we knew", "should have seen", "it was clear"],
    ),
    BiasCheck(
        name="Denominator Neglect",
        description="Focusing on the numerator (potential gain) while ignoring the denominator (probability).",
        check_question="Are we focused on upside magnitude while ignoring the probability of success?",
        red_flag_keywords=["10x potential", "could be huge", "massive upside", "moon", "100-bagger"],
    ),
    BiasCheck(
        name="Status Quo Bias",
        description="Preferring the current state of affairs, resisting change even when change is warranted.",
        check_question="Are we holding a position simply because it's what we've been doing?",
        red_flag_keywords=["keep holding", "no reason to change", "stay the course", "don't rock the boat"],
    ),
    BiasCheck(
        name="Framing Effect",
        description="Being influenced by how information is presented rather than its substance.",
        check_question="Would our conclusion change if the same data were presented differently?",
        red_flag_keywords=["only down", "still up", "relative to peers", "compared to the worst"],
    ),
    BiasCheck(
        name="Commitment/Consistency Bias",
        description="Sticking with a previous decision to appear consistent, even when evidence changes.",
        check_question="Are we sticking with our thesis because we publicly committed to it?",
        red_flag_keywords=["we already said", "as we predicted", "consistent with our view", "our thesis remains"],
    ),
    BiasCheck(
        name="Neglect of Probability",
        description="Ignoring base rates and probability when evaluating outcomes.",
        check_question="Have we considered the base rate of success for this type of investment?",
        red_flag_keywords=["this time is different", "unique situation", "exception", "unprecedented"],
    ),
]


def check_biases_in_reasoning(reasoning: str, signals: dict) -> list[BiasResult]:
    """Scan reasoning text and signals for potential cognitive biases.

    Args:
        reasoning: The textual reasoning from agent analysis.
        signals: Dict of signal data (e.g., agent confidence levels, tags).

    Returns:
        List of BiasResult, one per bias checked.
    """
    results: list[BiasResult] = []
    reasoning_lower = reasoning.lower()

    for bias in COGNITIVE_BIASES:
        matched_keywords: list[str] = []
        for keyword in bias.red_flag_keywords:
            if keyword.lower() in reasoning_lower:
                matched_keywords.append(keyword)

        is_flagged = len(matched_keywords) > 0
        if is_flagged:
            detail = (
                f"Potential {bias.name} detected. "
                f"Triggered by: {', '.join(matched_keywords)}. "
                f"Ask: {bias.check_question}"
            )
        else:
            detail = f"No {bias.name} indicators found."

        results.append(
            BiasResult(
                bias_name=bias.name,
                is_flagged=is_flagged,
                detail=detail,
            )
        )

    return results
