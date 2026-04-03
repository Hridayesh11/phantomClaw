import random

import streamlit as st


STOCKS = ["AAPL", "TSLA", "GOOGL", "MSFT"]
PRICE_RANGES = {
    "AAPL": (140.0, 220.0),
    "TSLA": (550.0, 1050.0),
    "GOOGL": (80.0, 170.0),
    "MSFT": (250.0, 470.0),
}


def generate_trade() -> dict:
    """Generate a mock trade for demo purposes."""
    action = random.choice(["BUY", "SELL"])
    stock = random.choice(STOCKS)
    lo, hi = PRICE_RANGES[stock]

    price = round(random.uniform(lo, hi), 2)
    confidence = round(random.uniform(0.5, 0.95), 3)

    return {
        "action": action,
        "stock": stock,
        "price": price,
        "confidence": confidence,
    }


def challenge_engine(trade: dict) -> tuple[str, str]:
    """Return one supporting reason and one opposing reason."""
    action = trade["action"]

    if action == "BUY":
        supporting = random.choice(
            [
                "Strong bullish momentum",
                "Breakout likely if support holds",
                "Momentum signals align with trend",
                "Positive order flow detected (mock)",
            ]
        )
        opposing = random.choice(
            [
                "Overbought conditions",
                "Volatility risk could spike sharply",
                "Nearby resistance may reject upside",
                "Confidence may be overstated in choppy markets",
            ]
        )
    else:
        supporting = random.choice(
            [
                "Bearish breakdown signals",
                "Risk-off market regime (mock)",
                "Momentum suggests downside continuation",
                "Trend weakness confirmed by indicators (mock)",
            ]
        )
        opposing = random.choice(
            [
                "Oversold bounce risk",
                "Mean reversion could invalidate the short thesis",
                "Support zone may absorb selling pressure",
                "Market could reverse abruptly without warning (mock)",
            ]
        )

    return supporting, opposing


def defense_engine(confidence: float) -> str:
    """Adversarial defense engine: classify risk based on confidence."""
    return "HIGH RISK" if confidence < 0.7 else "LOW RISK"


def trust_engine(risk_level: str) -> float:
    """Adaptive trust engine: lower trust when risk is high."""
    trust_score = 0.8
    if risk_level == "HIGH RISK":
        trust_score -= 0.3

    # Clamp between 0 and 1
    trust_score = max(0.0, min(1.0, trust_score))
    return trust_score


def execution_controller(trust_score: float) -> str:
    """Decide whether to execute or block based on trust score."""
    return "EXECUTE" if trust_score > 0.5 else "BLOCK"


def run_pipeline(trade: dict) -> dict:
    """Trade -> Challenge -> Risk -> Trust -> Decision."""
    supporting_reason, opposing_reason = challenge_engine(trade)
    risk_level = defense_engine(trade["confidence"])
    trust_score = trust_engine(risk_level)
    decision = execution_controller(trust_score)

    return {
        "trade": trade,
        "supporting_reason": supporting_reason,
        "opposing_reason": opposing_reason,
        "risk_level": risk_level,
        "trust_score": trust_score,
        "decision": decision,
    }


def _apply_fintech_style() -> None:
    st.markdown(
        """
        <style>
          body {
            background: radial-gradient(1200px circle at 20% 0%, #172554 0%, #070a12 55%, #05070f 100%);
            color: #e6edf3;
          }
          .title {
            font-size: 28px;
            font-weight: 800;
            letter-spacing: 0.2px;
          }
          .subtitle {
            color: rgba(230, 237, 243, 0.75);
          }
          .card {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 14px;
            padding: 16px;
            box-shadow: 0 10px 28px rgba(0,0,0,0.25);
          }
          .kpi {
            font-size: 22px;
            font-weight: 800;
          }
          .mini {
            color: rgba(230, 237, 243, 0.8);
            font-size: 13px;
          }
          .badge {
            border-radius: 999px;
            padding: 10px 14px;
            font-weight: 800;
            text-align: center;
            display: inline-block;
            border: 1px solid rgba(255,255,255,0.14);
          }
          .badge-execute { background: rgba(34,197,94,0.18); border-color: rgba(34,197,94,0.35); }
          .badge-block { background: rgba(239,68,68,0.16); border-color: rgba(239,68,68,0.35); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="PhantomClaw: Self-Defending Trading AI", layout="wide")
    _apply_fintech_style()

    st.markdown(
        """
        <div class="title">PhantomClaw: Self-Defending Trading AI</div>
        <div class="subtitle">A minimal secure validation pipeline for hackathon demos</div>
        """,
        unsafe_allow_html=True,
    )

    if "trade" not in st.session_state:
        st.session_state.trade = generate_trade()

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("Generate New Trade"):
            st.session_state.trade = generate_trade()

    pipeline = run_pipeline(st.session_state.trade)
    trade = pipeline["trade"]

    # Card layout
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    # Trade Proposal
    with c1:
        st.markdown(
            """
            <div class="card">
              <div class="mini">📊 Trade Proposal</div>
              <div class="mini" style="margin-top:4px;">
                A mock signal generated by the trading model.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='kpi'>{trade['action']} {trade['stock']}</div>", unsafe_allow_html=True)
        st.write(f"Price: ${trade['price']:.2f}")
        st.write(f"Model Confidence: {trade['confidence']:.3f}")

    # Decision Challenge
    with c2:
        st.markdown(
            """
            <div class="card">
              <div class="mini">⚖️ Decision Challenge</div>
              <div class="mini" style="margin-top:4px;">
                Two-sided critique: one support, one opposition.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("Support:", pipeline["supporting_reason"])
        st.write("Oppose:", pipeline["opposing_reason"])

    # Risk Analysis
    with c3:
        st.markdown(
            """
            <div class="card">
              <div class="mini">🛡️ Risk Analysis</div>
              <div class="mini" style="margin-top:4px;">
                Adversarial defense classifies risk from confidence.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write(f"Risk Level: {pipeline['risk_level']}")
        st.write(
            "Rule: confidence < 0.7 => HIGH RISK, else LOW RISK (mock defense heuristic)."
        )

    # Trust Score
    with c4:
        st.markdown(
            """
            <div class="card">
              <div class="mini">Trust Score</div>
              <div class="mini" style="margin-top:4px;">
                Start at 0.8, reduce when risk is high, then clamp to [0, 1].
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='kpi'>{pipeline['trust_score']:.2f}</div>", unsafe_allow_html=True)
        st.write("Rule: HIGH RISK => trust_score - 0.3")

    st.divider()

    # Final Decision
    d1, d2 = st.columns([2, 1])
    with d1:
        st.markdown(
            """
            <div class="card">
              <div class="mini">🚦 Final Decision</div>
              <div class="mini" style="margin-top:4px;">
                Execution controller uses trust threshold to block unsafe actions.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with d2:
        decision = pipeline["decision"]
        if decision == "EXECUTE":
            st.markdown(
                "<div class='badge badge-execute'>EXECUTE</div>", unsafe_allow_html=True
            )
        else:
            st.markdown("<div class='badge badge-block'>BLOCK</div>", unsafe_allow_html=True)

        st.write(
            "Rule: trust_score > 0.5 => EXECUTE, else BLOCK."
        )

    # Small explanation footer (helps demo narrative)
    st.caption(
        "All signals and outcomes are mocked. The focus is the validation pipeline and adversarial gating."
    )


if __name__ == "__main__":
    main()

