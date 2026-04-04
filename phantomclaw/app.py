import random
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

import streamlit as st
from alpaca_trade_api.rest import REST, TimeFrame


BASE_URL = "https://paper-api.alpaca.markets"
# Market data bars: IEX (not SIP) — matches free-tier / default paper data access.
ALPACA_BARS_FEED = "iex"

STOCKS = ["AAPL", "TSLA", "GOOGL", "MSFT"]

ADVERSARIAL_SCENARIOS = [
    "Fake breakout",
    "Market volatility spike",
    "Data manipulation signal",
    "Liquidity trap",
]

# Scenario severity ∈ [0, 1] for numerical risk blend
SCENARIO_SEVERITY = {
    "Fake breakout": 0.82,
    "Market volatility spike": 0.68,
    "Data manipulation signal": 0.92,
    "Liquidity trap": 0.74,
}


def _get_rest() -> Optional[REST]:
    try:
        key = st.secrets["ALPACA_API_KEY"]
        secret = st.secrets["ALPACA_SECRET_KEY"]
        return REST(key, secret, BASE_URL)
    except Exception:
        return None


def _bars_to_series(bars) -> tuple[list[float], list[float]]:
    try:
        if hasattr(bars, "df") and bars.df is not None and len(bars.df) > 0:
            df = bars.df
            closes = [float(x) for x in df["close"].tolist()]
            vols = [float(x) for x in df["volume"].tolist()]
            return closes, vols
    except Exception:
        pass
    closes, vols = [], []
    for bar in bars:
        closes.append(float(bar.c))
        vols.append(float(bar.v))
    return closes, vols


def generate_trade() -> Optional[dict]:
    """
    OpenClaw: build proposal from Alpaca daily bars — trend (5D vs 20D SMA),
    real last price, volatility- and trend-derived confidence, plus volume context.
    """
    api = _get_rest()
    if api is None:
        st.session_state["alpaca_data_error"] = "Alpaca API keys missing in Streamlit secrets."
        return None

    symbol = random.choice(STOCKS)
    try:
        # Explicit window: ~50 calendar days → comfortably ≥30 trading days (weekends/holidays).
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=50)
        start_s = start.strftime("%Y-%m-%d")
        end_s = end.strftime("%Y-%m-%d")
        bars = api.get_bars(
            symbol,
            TimeFrame.Day,
            start=start_s,
            end=end_s,
            adjustment="raw",
            feed=ALPACA_BARS_FEED,
        )
        closes, vols = _bars_to_series(bars)
    except Exception as e:
        st.session_state["alpaca_data_error"] = str(e)
        return None

    st.session_state.pop("alpaca_data_error", None)

    if len(closes) < 21 or len(vols) < 21:
        st.session_state["alpaca_data_error"] = f"Not enough bars for {symbol} (need ≥21 daily bars)."
        return None

    price = closes[-1]
    sma5 = statistics.mean(closes[-5:])
    sma20 = statistics.mean(closes[-20:])
    vol_avg = statistics.mean(vols[-20:])
    last_v = vols[-1]
    vol_ratio = last_v / vol_avg if vol_avg > 0 else 1.0

    if vol_ratio > 1.25:
        volume_note = f"Elevated — last session ~{vol_ratio:.2f}× 20D average volume"
    elif vol_ratio < 0.75:
        volume_note = f"Light — last session ~{vol_ratio:.2f}× 20D average volume"
    else:
        volume_note = f"Near average — ~{vol_ratio:.2f}× 20D average volume"

    rets = [(closes[i] / closes[i - 1] - 1.0) for i in range(-20, 0)]
    vol_daily = statistics.stdev(rets) if len(rets) > 1 else 0.0
    # Normalize: ~4% daily stdev → severity 1.0
    volatility_norm = max(0.0, min(1.0, vol_daily / 0.04))

    # Simple trend gate
    if sma5 > sma20 * 1.002:
        action = "BUY"
        trend = "bullish"
        reasoning = (
            f"Bullish structure: 5D SMA ({sma5:.2f}) above 20D SMA ({sma20:.2f}); "
            f"last close ${price:.2f} aligns with upward slope"
        )
    elif sma5 < sma20 * 0.998:
        action = "SELL"
        trend = "bearish"
        reasoning = (
            f"Bearish structure: 5D SMA ({sma5:.2f}) below 20D SMA ({sma20:.2f}); "
            f"last close ${price:.2f} aligns with downward slope"
        )
    else:
        trend = "neutral"
        if price >= sma20:
            action = "BUY"
        else:
            action = "SELL"
        reasoning = (
            f"Neutral regime: 5D ({sma5:.2f}) and 20D ({sma20:.2f}) SMAs compressed; "
            f"lean {action} from price vs 20D average (close ${price:.2f})"
        )

    strength = abs(sma5 - sma20) / price if price else 0.0
    confidence = 0.52 + min(0.43, strength * 22.0)
    if trend == "neutral":
        confidence = min(confidence, 0.72)

    scenario = random.choice(ADVERSARIAL_SCENARIOS)

    return {
        "action": action,
        "stock": symbol,
        "price": round(price, 2),
        "confidence": round(confidence, 3),
        "reasoning": reasoning,
        "scenario": scenario,
        "market_context": {
            "trend": trend,
            "sma5": sma5,
            "sma20": sma20,
            "volatility_daily": vol_daily,
            "volatility_norm": volatility_norm,
            "volume_ratio": vol_ratio,
            "volume_note": volume_note,
        },
    }


def _hydrate_trade_fields(trade: dict) -> None:
    if "market_context" not in trade:
        trade["market_context"] = {
            "trend": "unknown",
            "sma5": 0.0,
            "sma20": 0.0,
            "volatility_daily": 0.0,
            "volatility_norm": 0.5,
            "volume_ratio": 1.0,
            "volume_note": "Context unavailable (refresh trade from Alpaca).",
        }
    if "reasoning" not in trade:
        trade["reasoning"] = "Legacy proposal — click Generate New Trade for live context."
    if "scenario" not in trade:
        trade["scenario"] = ADVERSARIAL_SCENARIOS[
            abs(hash(trade.get("stock", ""))) % len(ADVERSARIAL_SCENARIOS)
        ]


def armoriq_validation(trade: dict) -> tuple[str, str]:
    """ArmorIQ validation: support/oppose grounded in OpenClaw thesis and tape context."""
    action = trade["action"]
    reasoning = trade.get("reasoning", "")
    ctx = trade.get("market_context", {})
    trend = ctx.get("trend", "unknown")
    vol_note = ctx.get("volume_note", "")

    if action == "BUY":
        supporting = random.choice(
            [
                f"Trend context is {trend}; long bias matches ArmorIQ momentum check (simulated).",
                f"OpenClaw narrative fits tape: “{reasoning[:80]}…”" if len(reasoning) > 80 else f"OpenClaw narrative fits tape: {reasoning}",
                f"Volume read: {vol_note}",
                "Structure favors buyers if 5D leadership holds over 20D (simulated).",
            ]
        )
        opposing = random.choice(
            [
                "ArmorIQ: extension risk — fade candidates on any adverse macro headline.",
                "Mean reversion could punish chasing near-term strength.",
                "Widening realized vol would erode edge even if trend looks fine.",
            ]
        )
    else:
        supporting = random.choice(
            [
                f"Trend context is {trend}; defensive/short-lean stance is internally consistent.",
                f"OpenClaw: {reasoning[:100]}…" if len(reasoning) > 100 else f"OpenClaw: {reasoning}",
                f"Participation: {vol_note}",
                "ArmorIQ sees asymmetric downside if support layers fail (simulated).",
            ]
        )
        opposing = random.choice(
            [
                "Oversold relief rallies can trap late shorts.",
                "ArmorIQ notes dip-buying could stabilize price quickly.",
                "Low liquidity can invert moves — false breakdown risk.",
            ]
        )

    return supporting, opposing


def compute_risk_score(confidence: float, scenario: str, volatility_norm: float) -> float:
    """Numerical risk ∈ [0, 1]: lower model confidence, higher scenario severity, higher vol → higher risk."""
    sev = SCENARIO_SEVERITY.get(scenario, 0.7)
    raw = 0.32 * (1.0 - confidence) + 0.38 * sev + 0.30 * volatility_norm
    return max(0.0, min(1.0, raw))


def risk_level_from_score(risk_score: float) -> str:
    return "HIGH RISK" if risk_score >= 0.52 else "LOW RISK"


def armoriq_trust(risk_score: float) -> float:
    """Map aggregate risk into trust ∈ [0, 1]."""
    trust = 0.88 - 0.72 * risk_score
    return max(0.0, min(1.0, trust))


def armoriq_execution_controller(trust_score: float) -> str:
    return "EXECUTE" if trust_score > 0.5 else "BLOCK"


def execute_trade(trade: dict, decision: str) -> str:
    """Place a paper-market order via Alpaca only when decision is EXECUTE."""
    if decision != "EXECUTE":
        return "Trade blocked by system ❌"
    try:
        api_key = st.secrets["ALPACA_API_KEY"]
        secret_key = st.secrets["ALPACA_SECRET_KEY"]
    except Exception as e:
        return f"Execution failed: {e}"

    symbol = trade["stock"]
    side = "buy" if trade["action"] == "BUY" else "sell"

    try:
        api = REST(api_key, secret_key, BASE_URL)
        api.submit_order(
            symbol=symbol,
            qty=1,
            side=side,
            type="market",
            time_in_force="gtc",
        )
        return "Order placed via Alpaca ✅"
    except Exception as e:
        return f"Execution failed: {e}"


def _already_holding(api: REST, symbol: str) -> bool:
    try:
        pos = api.get_position(symbol)
        return abs(float(pos.qty)) > 1e-9
    except Exception:
        return False


def _trade_fingerprint(trade: dict, already_holding: bool) -> tuple:
    mc = trade.get("market_context") or {}
    portfolio_blocks = already_holding and trade["action"] == "BUY"
    return (
        trade["action"],
        trade["stock"],
        trade["price"],
        trade["confidence"],
        trade.get("reasoning", ""),
        trade.get("scenario", ""),
        round(float(mc.get("volatility_norm", 0)), 4),
        mc.get("trend", ""),
        portfolio_blocks,
    )


def run_pipeline(trade: dict, *, already_holding: bool) -> dict:
    """OpenClaw → ArmorIQ Validation → ArmorIQ Defense (numeric risk) → Trust → Decision (+ portfolio gate)."""
    supporting_reason, opposing_reason = armoriq_validation(trade)
    scenario = trade["scenario"]
    vol_norm = float(trade.get("market_context", {}).get("volatility_norm", 0.5))

    risk_score = compute_risk_score(trade["confidence"], scenario, vol_norm)
    risk_level = risk_level_from_score(risk_score)
    trust_score = armoriq_trust(risk_score)
    controller_decision = armoriq_execution_controller(trust_score)

    # Block duplicate long exposure; still allow SELL when holding (reduce/exit).
    portfolio_blocks = already_holding and trade["action"] == "BUY"
    if portfolio_blocks:
        final_decision = "BLOCK"
        portfolio_note = (
            f"Portfolio gate: already long {trade['stock']} — BUY blocked to avoid duplicate exposure."
        )
    else:
        final_decision = controller_decision
        if already_holding and trade["action"] == "SELL":
            portfolio_note = f"Open position in {trade['stock']} — SELL allowed (exit/reduce)."
        elif not already_holding:
            portfolio_note = f"No open position in {trade['stock']} — portfolio gate passed."
        else:
            portfolio_note = f"Position state OK for proposed {trade['action']} on {trade['stock']}."

    return {
        "trade": trade,
        "supporting_reason": supporting_reason,
        "opposing_reason": opposing_reason,
        "scenario": scenario,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "trust_score": trust_score,
        "controller_decision": controller_decision,
        "decision": final_decision,
        "already_holding": already_holding,
        "portfolio_note": portfolio_note,
        "portfolio_blocks": portfolio_blocks,
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
          .pipeline-flow {
            color: rgba(147, 197, 253, 0.95);
            font-size: 15px;
            font-weight: 600;
            margin: 12px 0 18px 0;
            padding: 12px 16px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
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
          .openclaw-line {
            font-size: 17px;
            font-weight: 700;
            color: #e0e7ff;
            margin-top: 8px;
          }
          .badge {
            border-radius: 999px;
            padding: 10px 14px;
            font-weight: 800;
            text-align: center;
            display: inline-block;
            border: 1px solid rgba(255,255,255,0.14);
          }
          .badge-execute { background: rgba(34,197,94,0.18); border-color: rgba(34,197,94,0.35); color: #86efac; }
          .badge-block { background: rgba(239,68,68,0.16); border-color: rgba(239,68,68,0.35); color: #fca5a5; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _append_decision_log(
    fp: tuple, trade: dict, pipeline: dict, execution_result: str
) -> None:
    if st.session_state.get("decision_log_fp") == fp:
        return
    row = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "stock": trade["stock"],
        "risk_score": round(pipeline["risk_score"], 3),
        "trust": round(pipeline["trust_score"], 2),
        "decision": pipeline["decision"],
        "reasoning": trade.get("reasoning", "")[:200],
        "scenario": pipeline["scenario"],
        "execution_result": execution_result,
    }
    log = st.session_state.get("decision_log") or []
    log.append(row)
    st.session_state.decision_log = log[-10:]
    st.session_state.decision_log_fp = fp


def main() -> None:
    st.set_page_config(page_title="PhantomClaw: Self-Defending Trading AI", layout="wide")
    _apply_fintech_style()

    st.markdown(
        """
        <div class="title">PhantomClaw: Self-Defending Trading AI</div>
        <div class="subtitle">OpenClaw proposes · ArmorIQ validates and defends · Alpaca executes when allowed</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="pipeline-flow">🔁 System Pipeline: '
        "OpenClaw → ArmorIQ Validation → ArmorIQ Defense → Trust → Decision → Alpaca"
        "</div>",
        unsafe_allow_html=True,
    )

    if "trade" not in st.session_state:
        st.session_state.trade = None
    if "last_exec_fingerprint" not in st.session_state:
        st.session_state.last_exec_fingerprint = None
    if "execution_result_message" not in st.session_state:
        st.session_state.execution_result_message = ""
    if "decision_log" not in st.session_state:
        st.session_state.decision_log = []
    if "decision_log_fp" not in st.session_state:
        st.session_state.decision_log_fp = None

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        gen = st.button("Generate New Trade")
    if gen:
        nt = generate_trade()
        if nt:
            st.session_state.trade = nt

    if st.session_state.trade is None:
        with st.spinner("Loading market data from Alpaca…"):
            t0 = generate_trade()
        if t0:
            st.session_state.trade = t0
        else:
            err = st.session_state.get("alpaca_data_error", "Unknown error")
            st.error(f"Could not load market data: {err}")
            st.info("Add `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` to `.streamlit/secrets.toml`, then refresh.")
            st.stop()

    trade = st.session_state.trade
    _hydrate_trade_fields(trade)

    api = _get_rest()
    already_holding = _already_holding(api, trade["stock"]) if api else False

    pipeline = run_pipeline(trade, already_holding=already_holding)
    decision = pipeline["decision"]
    fp = _trade_fingerprint(trade, already_holding)

    if fp != st.session_state.last_exec_fingerprint:
        st.session_state.execution_result_message = execute_trade(trade, decision)
        st.session_state.last_exec_fingerprint = fp
        _append_decision_log(fp, trade, pipeline, st.session_state.execution_result_message)

    if st.session_state.get("alpaca_data_error") and gen:
        st.warning(st.session_state["alpaca_data_error"])

    ctx = trade.get("market_context", {})

    # Card layout
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    with c1:
        st.markdown(
            """
            <div class="card">
              <div class="mini">🧠 OpenClaw Agent</div>
              <div class="mini" style="margin-top:4px;">
                Live daily bars from Alpaca; signal from 5D vs 20D trend logic.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        reasoning = trade["reasoning"]
        because = reasoning[0].lower() + reasoning[1:] if reasoning else ""
        st.markdown(
            f"<div class='openclaw-line'>🧠 OpenClaw Decision: {trade['action']} {trade['stock']} "
            f"because {because}</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Market context**")
        st.caption(f"Trend: **{ctx.get('trend', '—')}** · 5D SMA {ctx.get('sma5', 0):.2f} · 20D SMA {ctx.get('sma20', 0):.2f}")
        st.caption(
            f"Volatility (20D daily return stdev): **{ctx.get('volatility_daily', 0) * 100:.2f}%** (norm {ctx.get('volatility_norm', 0):.2f})"
        )
        st.caption(f"Volume: {ctx.get('volume_note', '—')}")
        st.write(f"Last price: **${trade['price']:.2f}** · Model confidence: **{trade['confidence']:.3f}**")

    with c2:
        st.markdown(
            """
            <div class="card">
              <div class="mini">⚖️ ArmorIQ Validation Engine</div>
              <div class="mini" style="margin-top:4px;">
                ArmorIQ challenges the AI decision with opposing reasoning.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("👍 **Support:**", pipeline["supporting_reason"])
        st.write("👎 **Oppose:**", pipeline["opposing_reason"])

    with c3:
        st.markdown(
            """
            <div class="card">
              <div class="mini">🛡️ ArmorIQ Adversarial Defense</div>
              <div class="mini" style="margin-top:4px;">
                Numeric risk blends confidence, scenario severity, and realized volatility.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write(f"⚠️ **Detected Scenario:** {pipeline['scenario']}")
        st.markdown(f"<div class='kpi'>{pipeline['risk_score']:.2f}</div>", unsafe_allow_html=True)
        st.caption(f"Risk score (0–1) · Band: **{pipeline['risk_level']}**")

    with c4:
        st.markdown(
            """
            <div class="card">
              <div class="mini">📊 ArmorIQ Trust Engine</div>
              <div class="mini" style="margin-top:4px;">
                Trust derived from aggregate risk score; clamped to [0, 1].
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f"<div class='kpi'>{pipeline['trust_score']:.2f}</div>", unsafe_allow_html=True)
        st.caption(pipeline["portfolio_note"])

    st.divider()

    d1, d2 = st.columns([2, 1])
    with d1:
        st.markdown(
            """
            <div class="card">
              <div class="mini">🚦 ArmorIQ Execution Controller</div>
              <div class="mini" style="margin-top:4px;">
                ArmorIQ allows execution only if trust threshold is met and portfolio allows.
              </div>
              <div style="height:10px"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cd = pipeline["controller_decision"]
        st.caption(
            f"Controller (trust-only): **{cd}** · Final (with portfolio): **{decision}**"
        )

    with d2:
        if decision == "EXECUTE":
            st.markdown(
                "<div class='badge badge-execute'>EXECUTE</div>", unsafe_allow_html=True
            )
        else:
            st.markdown("<div class='badge badge-block'>BLOCK</div>", unsafe_allow_html=True)

        st.caption("EXECUTE if trust > 0.5 and portfolio allows (no duplicate BUY when already long).")

    with st.expander("📜 Explainability — why EXECUTE or BLOCK?", expanded=False):
        rs = pipeline["risk_score"]
        conf = trade["confidence"]
        sev = SCENARIO_SEVERITY.get(pipeline["scenario"], 0.7)
        vn = float(ctx.get("volatility_norm", 0.5))
        st.markdown(
            f"""
**1. Market & OpenClaw**  
- **Trend:** {ctx.get("trend", "—")} · **Thesis:** {trade.get("reasoning", "—")}

**2. Risk score ({rs:.2f} / 1.0)**  
- Blend: `0.32×(1−confidence) + 0.38×scenario_severity + 0.30×vol_norm`  
- Your inputs: confidence **{conf:.3f}** → (1−c) **{1 - conf:.3f}**; scenario **{pipeline["scenario"]}** → severity **{sev:.2f}**; vol norm **{vn:.2f}**

**3. Trust ({pipeline["trust_score"]:.2f})**  
- Mapped from risk: higher risk lowers trust (threshold **0.5** for controller).

**4. Portfolio**  
- {pipeline["portfolio_note"]}  
- Duplicate **BUY** while already long this symbol → **BLOCK** (SELL still allowed to reduce).

**5. Final**  
- **{decision}** — Alpaca is called **only** when the final decision is EXECUTE (same integration as before).
            """
        )

    if st.session_state.decision_log:
        st.divider()
        st.markdown("**📋 Decision Log** *(last 10)*")
        st.dataframe(list(reversed(st.session_state.decision_log)))

    st.divider()
    st.markdown("**💰 Execution powered by Alpaca Paper Trading**")
    st.markdown(
        """
        <div class="card">
          <div class="mini">Execution Result</div>
          <div class="mini" style="margin-top:4px;">
            Market orders (qty 1, GTC) only when the pipeline returns EXECUTE.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(st.session_state.execution_result_message)

    st.caption(
        "OpenClaw uses Alpaca market data; ArmorIQ scores risk and trust; Alpaca paper executes when allowed. "
        "Configure `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in Streamlit secrets."
    )


if __name__ == "__main__":
    main()
