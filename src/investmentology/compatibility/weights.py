from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from investmentology.models.signal import AgentSignalSet


@dataclass
class AgentWeights:
    warren: Decimal = field(default_factory=lambda: Decimal("0.25"))
    soros: Decimal = field(default_factory=lambda: Decimal("0.25"))
    simons: Decimal = field(default_factory=lambda: Decimal("0.25"))
    auditor: Decimal = field(default_factory=lambda: Decimal("0.25"))

    def as_dict(self) -> dict[str, Decimal]:
        return {
            "warren": self.warren,
            "soros": self.soros,
            "simons": self.simons,
            "auditor": self.auditor,
        }


_MIN_WEIGHT = Decimal("0.10")


@dataclass
class RegimeAdjustedWeights:
    weights: AgentWeights
    regime_score: Decimal  # -1 (bear) to +1 (bull)
    regime_label: str

    @classmethod
    def from_regime(
        cls, base_weights: AgentWeights, regime_score: Decimal
    ) -> RegimeAdjustedWeights:
        """Adjust agent weights based on market regime.

        Bear market (regime < -0.3):
          Warren +0.05, Soros +0.05, Simons -0.05, Auditor +0.05 (more defensive)
        Bull market (regime > 0.3):
          Warren -0.03, Soros +0.03, Simons +0.05, Auditor -0.03 (more offensive)
        Neutral: use base weights

        All weights must sum to 1.0. Min weight 0.10 per agent.
        """
        w = base_weights.warren
        s = base_weights.soros
        si = base_weights.simons
        a = base_weights.auditor

        if regime_score < Decimal("-0.3"):
            # Bear market: more defensive
            label = "bear"
            w += Decimal("0.05")
            s += Decimal("0.05")
            si -= Decimal("0.05")
            a += Decimal("0.05")
        elif regime_score > Decimal("0.3"):
            # Bull market: more offensive
            label = "bull"
            w -= Decimal("0.03")
            s += Decimal("0.03")
            si += Decimal("0.05")
            a -= Decimal("0.03")
        else:
            label = "neutral"

        # Enforce minimum weights and normalize to sum to 1.0.
        # Iteratively clamp floors and redistribute excess from above-floor
        # weights until all constraints are satisfied.
        vals = [w, s, si, a]
        for _ in range(10):  # converges in 2-3 iterations
            clamped = [max(v, _MIN_WEIGHT) for v in vals]
            total = sum(clamped, Decimal("0"))
            if total == Decimal("1"):
                vals = clamped
                break
            # Redistribute: scale only above-floor weights
            floored = [v == _MIN_WEIGHT and orig < _MIN_WEIGHT for v, orig in zip(clamped, vals)]
            excess = total - Decimal("1")
            flexible = [c for c, f in zip(clamped, floored) if not f]
            flex_total = sum(flexible, Decimal("0"))
            if flex_total == 0:
                # All at floor, just normalize
                vals = [v / total for v in clamped]
                break
            new_vals: list[Decimal] = []
            for c, f in zip(clamped, floored):
                if f:
                    new_vals.append(c)
                else:
                    new_vals.append(c - excess * (c / flex_total))
            vals = new_vals
        else:
            # Fallback normalization
            total = sum(vals, Decimal("0"))
            vals = [v / total for v in vals]

        w, s, si, a = vals

        # Round to avoid floating point drift, then fix rounding residual
        w = w.quantize(Decimal("0.0001"))
        s = s.quantize(Decimal("0.0001"))
        si = si.quantize(Decimal("0.0001"))
        a = a.quantize(Decimal("0.0001"))
        residual = Decimal("1") - (w + s + si + a)
        w += residual  # absorb any rounding residual into warren

        adjusted = AgentWeights(warren=w, soros=s, simons=si, auditor=a)
        return cls(weights=adjusted, regime_score=regime_score, regime_label=label)


def weighted_confidence(
    agent_signals: list[AgentSignalSet], weights: AgentWeights
) -> Decimal:
    """Calculate weighted average confidence from agent signals."""
    weight_map = weights.as_dict()
    total_weight = Decimal("0")
    weighted_sum = Decimal("0")

    for agent in agent_signals:
        agent_weight = weight_map.get(agent.agent_name, Decimal("0"))
        weighted_sum += agent.confidence * agent_weight
        total_weight += agent_weight

    if total_weight == 0:
        return Decimal("0")
    return weighted_sum / total_weight
