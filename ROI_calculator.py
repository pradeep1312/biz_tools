import math
import pandas as pd
import streamlit as st
from num2words import num2words

st.set_page_config(page_title="Working Capital Cycle ROI Calculator", layout="wide")

# ---------- Helpers ----------

def in_words(amount: float) -> str:
    """Return Indian-style words in lowercase, e.g., 'ten lakh thirty thousand'."""
    try:
        text = num2words(int(round(amount)), lang='en_IN').replace(",", "").lower()
        return text
    except Exception:
        return ""

def sidebar_hint(text: str):
    """Light, subtle hint text under inputs in sidebar."""
    if text:
        st.sidebar.markdown(
            f"<span style='font-size:11px; color:#888; font-style:italic;'>({text})</span>",
            unsafe_allow_html=True,
        )

def compute_emi_schedule_year(loan_amount: float,
                              annual_rate: float,
                              tenure_months: int):
    """
    Compute:
      - EMI per month
      - total interest paid in first year
      - total principal repaid in first year
      - outstanding loan after first year
    """
    if loan_amount <= 0 or annual_rate < 0 or tenure_months <= 0:
        return 0.0, 0.0, 0.0, loan_amount

    r_month = annual_rate / 12.0  # monthly rate (e.g. 12% -> 0.01)
    n = tenure_months

    if r_month > 0:
        factor = (1 + r_month) ** n
        emi = loan_amount * r_month * factor / (factor - 1)
    else:
        # 0% interest case
        emi = loan_amount / n

    outstanding = loan_amount
    total_interest_year = 0.0
    total_principal_year = 0.0

    # simulate up to 12 months (one year) or until loan fully repaid
    for m in range(1, 13):
        if m > n or outstanding <= 0:
            break

        interest_m = outstanding * r_month
        principal_m = emi - interest_m

        if principal_m > outstanding:
            principal_m = outstanding
            emi = interest_m + principal_m  # last payment adjusted

        outstanding -= principal_m

        total_interest_year += interest_m
        total_principal_year += principal_m

    return emi, total_interest_year, total_principal_year, outstanding

# ---------- Title & Description ----------

st.title("Working Capital Cycle ROI Calculator")

st.markdown("""
This tool simulates **working capital cycles with compounding**, including:

- Margin on revenue (converted to profit on cost)
- Fixed operating cost per cycle
- Annual fixed costs (salaries, rent, SG&A)
- Loan: **interest-only (CC/OD)** _or_ **EMI monthly (term loan)**
- Tax applied **once at year end** on cumulative profit
""")

# ---------- Inputs (Sidebar) ----------

st.sidebar.header("Inputs")

starting_capital = st.sidebar.number_input(
    "Starting Capital (your own capital)",
    min_value=0.0,
    value=1_000_000.0,
    step=50_000.0,
    format="%.2f",
)
sidebar_hint(in_words(starting_capital))

cycle_days = st.sidebar.number_input(
    "Cash Conversion Cycle (days)",
    min_value=1,
    value=45,
    step=1,
)

margin_pct = st.sidebar.number_input(
    "Gross Margin on Sales (%)",
    min_value=0.0,
    max_value=100.0,
    value=15.0,
    step=0.5,
)
margin = margin_pct / 100.0  # on revenue

fixed_cost_cycle = st.sidebar.number_input(
    "Fixed Operating Cost per Cycle",
    min_value=0.0,
    value=30_000.0,
    step=5_000.0,
    format="%.2f",
)
sidebar_hint(in_words(fixed_cost_cycle))

annual_fixed_cost = st.sidebar.number_input(
    "Annual Fixed Costs (Salaries, Rent, SG&A)",
    min_value=0.0,
    value=600_000.0,
    step=10_000.0,
    format="%.2f",
)
sidebar_hint(in_words(annual_fixed_cost))

loan_amount = st.sidebar.number_input(
    "Loan Amount",
    min_value=0.0,
    value=500_000.0,
    step=50_000.0,
    format="%.2f",
)
sidebar_hint(in_words(loan_amount))

loan_interest_pct = st.sidebar.number_input(
    "Loan Interest Rate per Year (%)",
    min_value=0.0,
    max_value=100.0,
    value=12.0,
    step=0.5,
)
loan_interest_rate = loan_interest_pct / 100.0

loan_type = st.sidebar.radio(
    "Loan Type",
    ["Interest-only (CC/OD style)", "EMI Monthly (Term Loan)"],
)

loan_tenure_months = 0
if loan_type == "EMI Monthly (Term Loan)":
    loan_tenure_months = st.sidebar.number_input(
        "Loan Tenure (months)",
        min_value=1,
        value=36,
        step=1,
    )

tax_rate_pct = st.sidebar.number_input(
    "Tax Rate on Annual Profit (%)",
    min_value=0.0,
    max_value=100.0,
    value=30.0,
    step=1.0,
)
tax_rate = tax_rate_pct / 100.0

round_cycles = st.sidebar.checkbox(
    "Floor number of cycles (ignore partial last cycle)",
    value=True,
)

# ---------- Basic Checks ----------

if cycle_days <= 0:
    st.error("Cash Conversion Cycle (days) must be > 0.")
    st.stop()

# ---------- Core Calculations ----------

raw_cycles = 365 / cycle_days
cycles = math.floor(raw_cycles) if round_cycles else raw_cycles

if cycles <= 0:
    st.warning("Number of cycles per year is 0. Increase the year length or decrease cycle_days.")
    st.stop()

# Annual fixed allocated per cycle
annual_fixed_per_cycle = annual_fixed_cost / cycles if cycles > 0 else 0.0

# Margin on revenue → markup on cost
# markup% = margin / (1 - margin)
markup = margin / (1 - margin) if 0 <= margin < 1 else 0.0

# ----- Loan behaviour -----

emi_monthly = 0.0
annual_loan_interest = 0.0
annual_principal_repayment = 0.0
loan_outstanding_end_year = loan_amount

if loan_amount > 0 and loan_interest_rate >= 0:
    if loan_type == "Interest-only (CC/OD style)":
        # Simple: pay only interest, no principal
        annual_loan_interest = loan_amount * loan_interest_rate
        annual_principal_repayment = 0.0
        emi_monthly = 0.0
        loan_outstanding_end_year = loan_amount
    else:
        # EMI Monthly (Term Loan)
        emi_monthly, total_int_year, total_prin_year, outstanding_after_year = \
            compute_emi_schedule_year(
                loan_amount=loan_amount,
                annual_rate=loan_interest_rate,
                tenure_months=int(loan_tenure_months),
            )
        annual_loan_interest = total_int_year
        annual_principal_repayment = total_prin_year
        loan_outstanding_end_year = outstanding_after_year

loan_interest_per_cycle = annual_loan_interest / cycles if cycles > 0 else 0.0
loan_principal_per_cycle = annual_principal_repayment / cycles if cycles > 0 else 0.0

# ----- Simulate cycles with compounding -----

capital = starting_capital
rows = []

for cycle in range(1, int(math.ceil(cycles)) + 1):
    # handle partial last cycle if not flooring
    cycle_fraction = 1.0
    if not round_cycles and cycle == math.ceil(cycles):
        cycle_fraction = cycles - math.floor(cycles)
        if cycle_fraction <= 0:
            cycle_fraction = 1.0

    starting_cap = capital

    gross_profit = starting_cap * markup * cycle_fraction
    fixed_this = fixed_cost_cycle * cycle_fraction
    annual_fixed_this = annual_fixed_per_cycle * cycle_fraction
    loan_interest_this = loan_interest_per_cycle * cycle_fraction
    loan_principal_this = loan_principal_per_cycle * cycle_fraction

    net_profit_before_tax = (
        gross_profit
        - fixed_this
        - annual_fixed_this
        - loan_interest_this
        - loan_principal_this
    )

    ending_capital = starting_cap + net_profit_before_tax

    rows.append(
        {
            "Cycle": cycle,
            "Starting Capital": round(starting_cap, 2),
            "Gross Profit": round(gross_profit, 2),
            "Fixed Cost (Cycle)": round(fixed_this, 2),
            "Allocated Annual Fixed": round(annual_fixed_this, 2),
            "Loan Interest": round(loan_interest_this, 2),
            "Loan Principal Repay": round(loan_principal_this, 2),
            "Net Profit Before Tax": round(net_profit_before_tax, 2),
            "Ending Capital": round(ending_capital, 2),
        }
    )

    capital = ending_capital

df = pd.DataFrame(rows)

ending_capital_before_tax = capital
cumulative_profit = ending_capital_before_tax - starting_capital

tax = max(cumulative_profit * tax_rate, 0.0)
net_income = cumulative_profit - tax
ending_capital_after_tax = starting_capital + net_income

roi_pct = (net_income / starting_capital * 100.0) if starting_capital > 0 else 0.0

# ---------- Output KPIs ----------

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Cycles per Year", f"{raw_cycles:.2f}")

with col2:
    st.metric("Simulated Cycles", f"{cycles:.2f}")

with col3:
    st.metric("Ending Capital (After Tax)", f"₹{ending_capital_after_tax:,.2f}")

with col4:
    st.metric("Annual ROI (After Tax)", f"{roi_pct:.2f}%")

st.write(f"Ending Capital in words: **{in_words(ending_capital_after_tax)}**")
st.write(f"Annual Net Income (After Tax): **₹{net_income:,.2f}** ({in_words(net_income)})")

# Loan info
st.markdown("---")
st.subheader("Loan Summary (1 Year View)")
loan_col1, loan_col2, loan_col3 = st.columns(3)

with loan_col1:
    st.write(f"Annual Interest Paid: **₹{annual_loan_interest:,.2f}**")

with loan_col2:
    st.write(f"Annual Principal Repaid: **₹{annual_principal_repayment:,.2f}**")

with loan_col3:
    st.write(f"Loan Outstanding After 1 Year: **₹{loan_outstanding_end_year:,.2f}**")

if loan_type == "EMI Monthly (Term Loan)" and emi_monthly > 0:
    st.write(f"Approx. EMI per month: **₹{emi_monthly:,.2f}**")

# ---------- Detailed Table & Chart ----------

st.markdown("---")
st.subheader("Per-Cycle Breakdown")
st.dataframe(df, use_container_width=True)

st.subheader("Capital Growth Over Cycles")
st.line_chart(df.set_index("Cycle")["Ending Capital"])
