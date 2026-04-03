# PhantomClaw: Self-Defending Trading AI

## Problem Statement
Trading signals can be spoofed, noisy, or adversarially influenced. For hackathon demos, we still need a clear way to validate a trade before allowing execution.

## Solution Overview
PhantomClaw is a minimal, clean “secure AI trading validation pipeline” prototype. It generates a mock trade, challenges it with a two-sided critique, classifies adversarial risk, adapts a trust score, and finally decides whether to execute or block.

## How It Works (Pipeline)
1. **Trade**: Randomly generate a mock trade proposal (BUY/SELL, stock, price, model confidence).
2. **Challenge**: Produce one supporting reason and one opposing reason.
3. **Risk**: Adversarial defense engine:
   - if `confidence < 0.7` => `HIGH RISK`
   - else => `LOW RISK`
4. **Trust**: Start `trust_score = 0.8`, reduce by **at least 0.3** when risk is HIGH, then clamp to `[0, 1]`.
5. **Decision**: Execution controller:
   - if `trust_score > 0.5` => `EXECUTE`
   - else => `BLOCK`

## Streamlit UI
The app presents a fintech-style dashboard with these sections:
`Trade Proposal`, `Decision Challenge`, `Risk Analysis`, `Trust Score`, and `Final Decision`.

Use the **Generate New Trade** button to rerun the full pipeline.

## How to Run
From the `phantomclaw/` directory:

```bash
pip install -r requirements.txt
streamlit run app.py
```

