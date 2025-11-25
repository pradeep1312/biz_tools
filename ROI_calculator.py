import math
import pandas as pd
import streamlit as st
from num2words import num2words

# Page config
st.set_page_config(page_title="Working Capital Cycle ROI Calculator", layout="wide")

# ---------- Helpers ----------

def in_words(amount: float) -> str:
    """Return Indian-style words in lowercase, e.g., 'ten lakh thirty thousand'."""
    try:
        text = num2words(int(round(amount)), lang='en_IN').replace(",", "").lower()
        return text
    except Exception:
        return ""

def hint_md(text: str):
    """Return styled markdown for light, small hint."""
    if not text:
        return ""
    return f"<div style='font-size:11px;color:#777;font-style:italic;margin-top:4px;'>({text})</div>"

def format_inr(x):
    """Format number in Indian style with rupee sign, no decimals if whole number."""
    try:
        if abs(round(x) - x) < 0.005:
            return f"₹{int(round(x)):,.0f}"
        return f"₹{x:,.2f}"
    except Exception:
        return str(x)

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

# ---------- Money input helper (dynamic words while typing) ----------
def money_input(label: str, default: float = 0.0, key: str | None = None):
    """
    Sidebar text input that accepts commas and shows live number-in-words.
    Returns float value (0.0 if invalid).
    """
    # display initial value with commas if user didn't type anything yet
    initial = f"{int(default):,}" if default is not None else ""
    txt = st.sidebar.text_input(label, value=initial, key=key)
    # clean input: remove commas and spaces
    cleaned = txt.replace(",", "").replace(" ", "")
    try:
        val = float(cleaned) if cleaned != "" else 0.0
    except:
        val = 0.0
    # show words hint dynamically
    words = in_words(val) if val else ""
    st.sidebar.markdown(hint_md(words), unsafe_allow_html=True)
    return val

# ---------- Title & Description ----------
st.title("Working Capital Cycle ROI Calculator")
st.markdown(
    "Simulates **working capital cycles with compounding**, including margin conversion, per-cycle fixed costs, annual fixed costs, loan (interest-only or EMI), and tax at year end."
)
st.markdown("---")

# ---------- Sidebar Inputs (grouped) ----------
st.sidebar.header("Inputs")

# Group 1: Capital & Cycle
st.sidebar.subheader("Capital & Cycle")
starting_capital = money_input("Starting Capital (your own capital)", default=1_000_000.0, key="start_cap")

cycle_days = st.sidebar.number_input(
    "Cash Conversion Cycle (days)", min_value=1, value=45, step=1
)

# Group 2: Margins & Costs
st.sidebar.subheader("Margins & Costs")
margin_pct = st.sidebar.number_input(
    "Gross Margin on Sales (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5
)
margin = margin_pct / 100.0  # on revenue

fixed_cost_cycle = money_input("Fixed Operating Cost per Cycle", default=30_000.0, key="fixed_cycle")

annual_fixed_cost = money_input("Annual Fixed Costs (Salaries, Rent, SG&A)", default=600_000.0, key="annual_fixed")

# Group 3: Loan
st.sidebar.subheader("Loan")
loan_amount = money_input("Loan Amount", default=500_000.0, key="loan_amt")

loan_interest_pct = st.sidebar.number_input(
    "Loan Interest Rate per Year (%)",
    min_value=0.0,
    max_value=100.0,
    value=12.0,
    step=0.5,
)
loan_interest_rate = loan_interest_pct / 100.0

loan_type = st.sidebar.radio(
    "Loan Type", ["Interest-only (CC/OD style)", "EMI Monthly (Term Loan)"]
)

loan_tenure_months = 0
if loan_type == "EMI Monthly (Term Loan)":
    loan_tenure_months = st.sidebar.number_input(
        "Loan Tenure (months)", min_value=1, value=36, step=1
    )

# Group 4: Tax & Options
st.sidebar.subheader("Tax & Options")
tax_rate_pct = st.sidebar.number_input(
    "Tax Rate on Annual Profit (%)", min_value=0.0, max_value=100.0, value=30.0, step=1.0
)
tax_rate = tax_rate_pct / 100.0

round_cycles = st.sidebar.checkbox("Floor number of cycles (ignore partial last cycle)", value=True)

# ---------- Basic Checks ----------
if cycle_days <= 0:
    st.error("Cash Conversion Cycle (days) must be > 0.")
    st.stop()

# ---------- Core Calculations (identical logic) ----------
raw_cycles = 365 / cycle_days
cycles = math.floor(raw_cycles) if round_cycles else raw_cycles

if cycles <= 0:
    st.warning("Number of cycles per year is 0. Increase cycle_days or adjust settings.")
    st.stop()

annual_fixed_per_cycle = annual_fixed_cost / cycles if cycles > 0 else 0.0

# Convert margin on sales -> markup on cost
markup = margin / (1 - margin) if 0 <= margin < 1 else 0.0

# Loan behavior calculations
emi_monthly = 0.0
annual_loan_interest = 0.0
annual_principal_repayment = 0.0
loan_outstanding_end_year = loan_amount

if loan_amount > 0 and loan_interest_rate >= 0:
    if loan_type == "Interest-only (CC/OD style)":
        annual_loan_interest = loan_amount * loan_interest_rate
        annual_principal_repayment = 0.0
        emi_monthly = 0.0
        loan_outstanding_end_year = loan_amount
    else:
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

# Simulate cycles with compounding
capital = starting_capital
rows = []

for cycle in range(1, int(math.ceil(cycles)) + 1):
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

# ---------- Output area with Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["Summary", "Loan Summary", "Cycle Breakdown", "Growth Chart"])

with tab1:
    st.subheader("Summary")
    k1, k2, k3, k4 = st.columns([1.2,1,1,1])
    k1.metric("Cycles / Year", f"{raw_cycles:.2f}")
    k2.metric("Simulated Cycles", f"{cycles:.2f}")
    k3.metric("Ending Capital (After Tax)", format_inr(ending_capital_after_tax))
    k4.metric("Annual ROI (After Tax)", f"{roi_pct:.2f}%")

    st.markdown("")
    c1, c2 = st.columns([2,1])
    with c1:
        st.write("**Annual Net Income (After Tax):**", format_inr(net_income))
        st.caption(in_words(net_income))
        st.write("**Cumulative Profit (Before Tax):**", format_inr(cumulative_profit))
    with c2:
        st.write("**Starting Capital:**")
        st.write(format_inr(starting_capital))
        st.caption(in_words(starting_capital))

with tab2:
    st.subheader("Loan Summary (1 Year View)")
    st.write(f"**Loan Type:** {loan_type}")
    st.write(f"**Loan Amount:** {format_inr(loan_amount)}", " — ", in_words(loan_amount))
    st.write(f"**Annual Interest Paid:** {format_inr(annual_loan_interest)}")
    st.write(f"**Annual Principal Repaid:** {format_inr(annual_principal_repayment)}")
    st.write(f"**Loan Outstanding After 1 Year:** {format_inr(loan_outstanding_end_year)}")
    if loan_type == "EMI Monthly (Term Loan)" and emi_monthly > 0:
        st.write(f"Approx. EMI per month: **{format_inr(emi_monthly)}**")

with tab3:
    st.subheader("Per-Cycle Breakdown")
    st.dataframe(df, use_container_width=True)

with tab4:
    st.subheader("Capital Growth Over Cycles")
    st.line_chart(df.set_index("Cycle")["Ending Capital"])

# Footer spacing
st.markdown("---")
st.caption("Tip: change inputs on the left — number-in-words hints update instantly as you type.")
