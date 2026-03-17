Python 3.14.3 (v3.14.3:323c59a5e34, Feb  3 2026, 11:41:37) [Clang 16.0.0 (clang-1600.0.26.6)] on darwin
Enter "help" below or click "Help" above for more information.
>>> import streamlit as st
... import math
... import json
... import io
... import csv
... 
... # ───────────────────────────────────────────────────────────────
... #  KPMG Partner Profit Allocation & Compensation Tool 
... #  Equity Partner Model 
... # ───────────────────────────────────────────────────────────────
... 
... # --- Core Parameters (same as terminal script) -----------------
... 
... SENIORITY_TIERS = {
...     "Junior Partner":        {"draw_multiplier": 1.00, "dist_multiplier": 1.00},
...     "Senior Partner":        {"draw_multiplier": 1.25, "dist_multiplier": 1.30},
...     "Principal / Director":  {"draw_multiplier": 1.50, "dist_multiplier": 1.60},
...     "Managing Director":     {"draw_multiplier": 1.75, "dist_multiplier": 1.90},
... }
... 
... ROLE_SUPPLEMENTS = {
...     "No Special Role":           0,
...     "Office Managing Partner":   75_000,
...     "Practice Leader":           50_000,
...     "Regional Managing Partner": 120_000,
...     "National Practice Leader":  100_000,
... }
... 
... PERFORMANCE_RATINGS = {
...     "Below Expectations":   0.80,
...     "Meets Expectations":   1.00,
...     "Exceeds Expectations": 1.15,
...     "Outstanding":          1.30,
... }
... 
... FIRM_PERFORMANCE_TIERS = {
...     "Below Target (<90% of Plan)":     0.85,
    "On Target (90–100% of Plan)":     1.00,
    "Above Target (101–115% of Plan)": 1.12,
    "Exceptional (>115% of Plan)":     1.25,
}

BASE_ANNUAL_DRAW          = 300_000
DEFAULT_PROFIT_POOL       = 5_000_000
DEFAULT_CAPITAL_RATE      = 0.05
SE_TAX_RATE               = 0.1413
FEDERAL_INCOME_TAX_RATE   = 0.37
DEFAULT_STATE_TAX_RATE    = 0.05

KPMG_BLUE = "#00338D"   # close to official KPMG blue
KPMG_LIGHT_BLUE = "#0077C8"
KPMG_GREY = "#6C757D"


# --- Calculation Logic -----------------------------------------

def calculate_compensation(
    seniority_label: str,
    role_label: str,
    performance_label: str,
    firm_perf_label: str,
    profit_pool: float,
    equity_units: float,
    total_units: float,
    draw_freq: str,
    custom_draw: float | None,
    capital_rate: float,
    state_tax_rate: float,
    other_deductions: float,
):
    seniority = SENIORITY_TIERS[seniority_label]
    perf_mult = PERFORMANCE_RATINGS[performance_label]
    firm_mult = FIRM_PERFORMANCE_TIERS[firm_perf_label]
    role_supplement = ROLE_SUPPLEMENTS[role_label]

    if custom_draw is not None and custom_draw > 0:
        annual_draw = custom_draw
    else:
        annual_draw = BASE_ANNUAL_DRAW * seniority["draw_multiplier"] * perf_mult

    equity_pct = equity_units / total_units if total_units > 0 else 0
    raw_dist = profit_pool * equity_pct

    dist_share = (
        raw_dist
        * seniority["dist_multiplier"]
        * perf_mult
        * firm_mult
    )

    gross = annual_draw + dist_share + role_supplement

    capital_contrib = annual_draw * capital_rate
    se_tax = gross * SE_TAX_RATE
    fed_tax = gross * FEDERAL_INCOME_TAX_RATE
    state_tax = gross * state_tax_rate
    total_tax = se_tax + fed_tax + state_tax
    total_deductions = capital_contrib + total_tax + other_deductions
    net_income = gross - total_deductions

    periods = 12 if draw_freq == "Monthly" else 4
    draw_per_period = annual_draw / periods if periods else 0

    eff_rate = (total_tax / gross * 100) if gross > 0 else 0

    return {
        "annual_draw": annual_draw,
        "draw_per_period": draw_per_period,
        "draw_periods": periods,
        "role_supplement": role_supplement,
        "equity_pct": equity_pct,
        "raw_dist_share": raw_dist,
        "dist_share": dist_share,
        "gross": gross,
        "capital_contrib": capital_contrib,
        "capital_rate": capital_rate,
        "se_tax": se_tax,
        "fed_tax": fed_tax,
        "state_tax": state_tax,
        "state_rate": state_tax_rate,
        "other_deductions": other_deductions,
        "total_deductions": total_deductions,
        "net_income": net_income,
        "effective_tax_rate": eff_rate,
    }


# --- Session state for multiple partners ------------------------

if "partners" not in st.session_state:
    st.session_state["partners"] = []  # list of dicts, one per partner row


# --- Layout & UI -----------------------------------------------

st.set_page_config(
    page_title="KPMG Partner Profit Allocation Tool",
    page_icon="💼",
    layout="wide",
)

# Header
st.markdown(
    f"""
    <div style="background-color:{KPMG_BLUE};padding:1.1rem 1.5rem;border-radius:4px;">
      <h2 style="color:white;margin:0;">KPMG Partner Profit Allocation & Compensation Tool</h2>
      <p style="color:#DDE2EB;margin:0.2rem 0 0 0;font-size:0.9rem;">
        Equity Partner Model – Consulting & Tax | Internal Illustrative Tool (not tax advice)
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")

with st.sidebar:
    st.markdown(
        f"### Configuration\n"
        f"<span style='color:{KPMG_GREY};font-size:0.9rem;'>"
        f"Set firm-wide and tax assumptions here."
        f"</span>",
        unsafe_allow_html=True,
    )

    st.subheader("Firm Performance & Profit Pool")
    firm_perf_label = st.selectbox(
        "Firm Performance vs Annual Plan",
        list(FIRM_PERFORMANCE_TIERS.keys()),
        index=1,
    )
    default_pool = DEFAULT_PROFIT_POOL
    profit_pool = st.number_input(
        "Distributable Profit Pool (USD)",
        min_value=0.0,
        step=250_000.0,
        value=float(default_pool),
        format="%.0f",
    )

    st.subheader("Tax & Capital Assumptions")
    capital_rate = st.slider(
        "Capital Contribution Rate (% of Draw)",
        min_value=0.0,
        max_value=15.0,
        value=DEFAULT_CAPITAL_RATE * 100,
        step=0.5,
    ) / 100.0

    state_tax_rate = st.slider(
        "State Income Tax Rate (%)",
        min_value=0.0,
        max_value=15.0,
        value=DEFAULT_STATE_TAX_RATE * 100,
        step=0.5,
    ) / 100.0

    st.caption(
        "Self-employment and federal income tax rates are held constant "
        "for illustration (14.13% SE, 37% federal)."
    )

# Main inputs
col_profile, col_econ = st.columns([1.2, 1.0])

with col_profile:
    st.markdown(f"#### Partner profile", unsafe_allow_html=True)

    name = st.text_input("Partner Name", value="")
    title = st.text_input("Title", value="Partner")
    office = st.text_input("Office / Region", value="New York")
    service_line = st.text_input(
        "Service Line", value="Tax"
    )
    years_as_partner = st.number_input(
        "Years as Partner",
        min_value=0,
        max_value=50,
        value=10,
        step=1,
    )

    seniority_label = st.selectbox(
        "Seniority Tier",
        list(SENIORITY_TIERS.keys()),
        index=1,
    )

    role_label = st.selectbox(
        "Leadership Role",
        list(ROLE_SUPPLEMENTS.keys()),
        index=0,
    )

    performance_label = st.selectbox(
        "Individual Performance Rating",
        list(PERFORMANCE_RATINGS.keys()),
        index=2,
    )

    draw_freq = st.radio(
        "Draw Frequency",
        options=["Monthly", "Quarterly"],
        index=0,
        horizontal=True,
    )

with col_econ:
    st.markdown(f"#### Economic inputs", unsafe_allow_html=True)

    st.markdown("**Equity Units / Points**")
    equity_units = st.number_input(
        "Partner's Equity Units / Points",
        min_value=1.0,
        max_value=10_000.0,
        value=150.0,
        step=10.0,
    )
    total_units = st.number_input(
        "Total Firm Equity Units / Points",
        min_value=equity_units,
        max_value=100_000.0,
        value=2_500.0,
        step=100.0,
    )

    st.markdown("**Production & Relationships**")
    revenue_billed = st.number_input(
        "Revenue Originated (USD)",
        min_value=0.0,
        value=8_500_000.0,
        step=250_000.0,
        format="%.0f",
    )
    new_business = st.number_input(
        "New Business Won (USD)",
        min_value=0.0,
        value=2_000_000.0,
        step=100_000.0,
        format="%.0f",
    )
    client_count = st.number_input(
        "Active Client Relationships",
        min_value=0,
        max_value=9_999,
        value=45,
        step=1,
    )

    st.markdown("**Overrides & Other Deductions**")
    use_custom_draw = st.checkbox(
        "Override calculated annual draw with custom amount",
        value=False,
    )
    custom_draw = None
    if use_custom_draw:
        custom_draw = st.number_input(
            "Custom Annual Draw (USD)",
            min_value=0.0,
            value=600_000.0,
            step=50_000.0,
            format="%.0f",
        )

    other_deductions = st.number_input(
        "Other Annual Deductions / Withholdings (USD)",
        min_value=0.0,
        value=0.0,
        step=10_000.0,
        format="%.0f",
    )

# Run calculation
calc = calculate_compensation(
    seniority_label=seniority_label,
    role_label=role_label,
    performance_label=performance_label,
    firm_perf_label=firm_perf_label,
    profit_pool=profit_pool,
    equity_units=equity_units,
    total_units=total_units,
    draw_freq=draw_freq,
    custom_draw=custom_draw,
    capital_rate=capital_rate,
    state_tax_rate=state_tax_rate,
    other_deductions=other_deductions,
)

# Output – 3 columns: headline, income, deductions
st.markdown("---")

st.markdown(
    f"<h4 style='color:{KPMG_BLUE};margin-bottom:0.5rem;'>"
    f"Partner Allocation Summary</h4>",
    unsafe_allow_html=True,
)

headline_col, income_col, ded_col = st.columns([1.1, 1.1, 1.0])

with headline_col:
    st.markdown("**Partner snapshot**")
    st.write(f"**Name:** {name or '—'}")
    st.write(f"**Title:** {title}")
    st.write(f"**Office:** {office}")
    st.write(f"**Service Line:** {service_line}")
    st.write(f"**Years as Partner:** {years_as_partner}")
    st.write(f"**Seniority:** {seniority_label}")
    st.write(f"**Role:** {role_label}")
    st.write(f"**Performance:** {performance_label}")
    st.write(f"**Firm Performance:** {firm_perf_label}")
    st.write(
        f"**Equity:** {calc['equity_pct']*100:.4f}% "
        f"({equity_units:,.0f} / {total_units:,.0f} units)"
    )
    st.write(f"**Revenue Originated:** ${revenue_billed:,.0f}")
    st.write(f"**New Business:** ${new_business:,.0f}")
    st.write(f"**Active Clients:** {client_count}")

with income_col:
    st.markdown("**Income components**")
    st.metric(
        "Gross Compensation",
        f"${calc['gross']:,.0f}",
    )
    st.write(
        f"Annual Draw (performance-adjusted): "
        f"**${calc['annual_draw']:,.0f}**"
    )
    st.write(
        f"{draw_freq} Draw ({calc['draw_periods']}x/year): "
        f"${calc['draw_per_period']:,.0f}"
    )
    if calc["role_supplement"] > 0:
        st.write(
            f"Leadership Role Supplement: "
            f"${calc['role_supplement']:,.0f}"
        )
    st.write(f"Raw Distributive Share: ${calc['raw_dist_share']:,.0f}")
    st.write(
        f"Adjusted Distributive Share: "
        f"**${calc['dist_share']:,.0f}**"
    )

with ded_col:
    st.markdown("**Deductions & obligations**")
    st.metric(
        "Estimated Net Income",
        f"${calc['net_income']:,.0f}",
    )
    st.write(
        f"Capital Contribution ({calc['capital_rate']*100:.1f}% draw): "
        f"${calc['capital_contrib']:,.0f}"
    )
    st.write(f"Self-Employment Tax (~14.1%): ${calc['se_tax']:,.0f}")
    st.write(f"Federal Income Tax (~37.0%): ${calc['fed_tax']:,.0f}")
    st.write(
        f"State Income Tax ({calc['state_rate']*100:.1f}%): "
        f"${calc['state_tax']:,.0f}"
    )
    if calc["other_deductions"] > 0:
        st.write(f"Other Deductions: ${calc['other_deductions']:,.0f}")
    st.write(f"Total Deductions: **${calc['total_deductions']:,.0f}**")
    st.write(
        f"Effective Tax Rate (SE + Fed + State): "
        f"**{calc['effective_tax_rate']:.1f}%**"
    )

# --- Add to multi-partner summary --------------------------------

st.markdown("")
if st.button("➕ Save this partner to session summary"):
    partner_row = {
        "Name": name or "",
        "Title": title,
        "Office": office,
        "Service Line": service_line,
        "Seniority": seniority_label,
        "Role": role_label,
        "Performance": performance_label,
        "Firm Performance": firm_perf_label,
        "Equity Units": equity_units,
        "Total Units": total_units,
        "Equity %": round(calc["equity_pct"] * 100, 4),
        "Gross Compensation": round(calc["gross"], 2),
        "Net Income": round(calc["net_income"], 2),
        "Annual Draw": round(calc["annual_draw"], 2),
        "Draw Frequency": draw_freq,
        "Draw / Period": round(calc["draw_per_period"], 2),
        "Distributive Share": round(calc["dist_share"], 2),
        "Capital Contribution": round(calc["capital_contrib"], 2),
        "SE Tax": round(calc["se_tax"], 2),
        "Federal Tax": round(calc["fed_tax"], 2),
        "State Tax": round(calc["state_tax"], 2),
        "Other Deductions": round(calc["other_deductions"], 2),
        "Total Deductions": round(calc["total_deductions"], 2),
        "Effective Tax Rate %": round(calc["effective_tax_rate"], 2),
        "Revenue Originated": revenue_billed,
        "New Business Won": new_business,
        "Active Clients": client_count,
    }
    st.session_state["partners"].append(partner_row)
    st.success("Partner added to session summary.")

# --- Multi-partner summary & download buttons -------------------

if st.session_state["partners"]:
    st.markdown("---")
    st.markdown(
        f"<h4 style='color:{KPMG_BLUE};margin-bottom:0.5rem;'>"
        f"Session Summary – Partner Comparison</h4>",
        unsafe_allow_html=True,
    )

    # Show key columns in a compact table
    display_cols = [
        "Name",
        "Office",
        "Service Line",
        "Seniority",
        "Role",
        "Performance",
        "Equity %",
        "Gross Compensation",
        "Net Income",
        "Effective Tax Rate %",
    ]

    summary_data = [
        {col: row.get(col) for col in display_cols}
        for row in st.session_state["partners"]
    ]

    st.dataframe(summary_data, use_container_width=True)

    # Prepare CSV and JSON
    full_data = st.session_state["partners"]

    # CSV
    csv_buffer = io.StringIO()
    if full_data:
        writer = csv.DictWriter(csv_buffer, fieldnames=full_data[0].keys())
        writer.writeheader()
        for r in full_data:
            writer.writerow(r)
    csv_bytes = csv_buffer.getvalue().encode("utf-8")

    # JSON
    json_bytes = json.dumps(full_data, indent=2).encode("utf-8")

    dcol1, dcol2, dcol3 = st.columns([0.4, 0.4, 0.2])

    with dcol1:
        st.download_button(
            label="⬇️ Download summary as CSV",
            data=csv_bytes,
            file_name="kpmg_partner_summary.csv",
            mime="text/csv",
        )

    with dcol2:
        st.download_button(
            label="⬇️ Download full details as JSON",
            data=json_bytes,
            file_name="kpmg_partner_summary.json",
            mime="application/json",
        )

    with dcol3:
        if st.button("🗑 Clear session summary"):
            st.session_state["partners"] = []
            st.experimental_rerun()

# Optional: raw JSON for current partner
with st.expander("View raw allocation data for current partner", expanded=False):
    st.json(
        {
            "partner": {
                "name": name,
                "title": title,
                "office": office,
                "service_line": service_line,
                "years_as_partner": years_as_partner,
            },
            "classification": {
                "seniority_tier": seniority_label,
                "special_role": role_label,
                "performance_rating": performance_label,
                "firm_performance": firm_perf_label,
                "equity_units": equity_units,
                "total_firm_units": total_units,
                "equity_pct": round(calc["equity_pct"] * 100, 4),
            },
            "revenue_metrics": {
                "revenue_originated": revenue_billed,
                "new_business_won": new_business,
                "active_clients": client_count,
            },
            "compensation": {
                "annual_draw": round(calc["annual_draw"], 2),
                "draw_frequency": draw_freq,
                "draw_per_period": round(calc["draw_per_period"], 2),
                "role_supplement": round(calc["role_supplement"], 2),
                "distributive_share_adjusted": round(calc["dist_share"], 2),
                "gross_compensation": round(calc["gross"], 2),
            },
            "deductions": {
                "capital_contribution": round(calc["capital_contrib"], 2),
                "se_tax": round(calc["se_tax"], 2),
                "federal_income_tax": round(calc["fed_tax"], 2),
                "state_income_tax": round(calc["state_tax"], 2),
                "other_deductions": round(calc["other_deductions"], 2),
                "total_deductions": round(calc["total_deductions"], 2),
            },
            "net": {
                "estimated_net_income": round(calc["net_income"], 2),
                "effective_tax_rate_pct": round(calc["effective_tax_rate"], 2),
            },
        }
    )

st.markdown(
    f"<p style='color:{KPMG_GREY};font-size:0.8rem;margin-top:1.5rem;'>"
    "This tool is illustrative only and does not constitute tax, legal, or accounting advice. "
    "Partner compensation decisions should be made in accordance with KPMG policies and governance."
    "</p>",
    unsafe_allow_html=True,
