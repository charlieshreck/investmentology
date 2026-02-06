# Investmentology

AI-powered institutional-grade investment advisory platform. A hedge fund analyst in a box.

## Architecture

Sequential 6-layer pipeline that filters 5000+ stocks down to executable paper trades:

1. **Quantitative Gate** - Greenblatt Magic Formula (ROIC + Earnings Yield)
2. **Competence Filter** - Buffett-style circle of competence + moat analysis
3. **Multi-Agent Analysis** - 4 independent AI agents with weighted consensus
4. **Adversarial Check** - Munger-style bias detection and thesis destruction
5. **Timing & Sizing** - Howard Marks cycle detection + Kelly Criterion
6. **Continuous Learning** - Full decision registry with calibration feedback

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Design Documentation

Full architectural docs in [Outline](https://outline.kernow.io/collection/learning-investmentology-4A1fLp8aqX).

## Status

Phase 1: Foundation (Quant Gate + Decision Registry)
