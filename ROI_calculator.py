import math
import pandas as pd
import streamlit as st
from num2words import num2words
from authlib.integrations.requests_client import OAuth2Session

# ========== AUTH0 CONFIG FROM STREAMLIT SECRETS ==========

auth0_domain = st.secrets["auth0_domain"]
auth0_client_id = st.secrets["auth0_client_id"]
auth0_client_secret = st.secrets["auth0_client_secret"]
auth0_redirect_uri = st.secrets["auth0_redirect_uri"]

authorize_url = f"https://{auth0_domain}/authorize"
token_url = f"https://{auth0_domain}/oauth/token"
userinfo_url = f"https://{auth0_domain}/userinfo"


# ========== GOOGLE LOGIN HELPERS ==========

def login_button():
    oauth = OAuth2Session(
        client_id=auth0_client_id,
        client_secret=auth0_client_secret,
        scope="openid profile email",
        redirect_uri=auth0_redirect_uri,
    )
    uri, _ = oauth.create_authorization_url(authorize_url)
    st.markdown(f"[Login with Google]({uri})")


def handle_callback():
    params = st.experimental_get_query_params()

    if "code" in params:
        code = params["code"][0]

        oauth = OAuth2Session(
            client_id=auth0_client_id,
            client_secret=auth0_client_secret,
            scope="openid profile email",
            redirect_uri=auth0_redirect_uri,
        )

        token = oauth.fetch_token(
            token_url=token_url,
            code=code,
        )

        userinfo = oauth.get(userinfo_url, token=token).json()
        st.session_state["user"] = userinfo
        return True

    return False


# ========== APPLY AUTH BEFORE APP CONTENT ==========

if "user" not in st.session_state:
    st.title("Login Required")
    if handle_callback():
        st.experimental_rerun()
    login_button()
    st.stop()


# ========== USER LOGGED IN ==========

userinfo = st.session_state["user"]

st.sidebar.success(f"Welcome {userinfo['name']}")
st.sidebar.write(userinfo["email"])

if st.sidebar.button("Logout"):
    st.session_state.clear()
    st.experimental_rerun()


# ===================================================================
# ========== WORKING CAPITAL ROI CALCULATOR START ===================
# ===================================================================

st.set_page_config(page_title="Working Capital Cycle ROI Calculator", layout="wide")


# ---------- Helpers ----------
def in_words(amount: float) -> str:
    """Return Indian-style words in lowercase, e.g. 'ten lakh thirty thousand'."""
    try:
        text = num2words(int(round(amount)), lang="en_IN").replace(",", "").lower()
        return text
    except Exception:
        return ""


def sidebar_hint(text: str):
    """Light grey hint under money inputs."""
    if text:
        st.sidebar.markdown(
            f"<span style='font-size:11px; color:#888; font-style:italic;'>({text})</span>",
            unsafe_allow_html=True,
        )


def compute_emi_schedule_year(loan_amount, annual_rate, tenure_months):
    """Return EMI, annual interest, annual principal, outstanding after 1 year."""
    if loan_amount <= 0 or annual_rate < 0 or tenure_months <= 0:
        return 0.0, 0.0, 0.0, loan_amount

    r_month = annual_rate / 12.0
    n = tenure_months

    if r_month > 0:
        factor = (1 + r_month) ** n
        emi = loan_amount * r_month * factor / (factor - 1)
    else:
        emi = loan_amount / n

    outstanding = loan_amount
    total_interest_year = 0.0
    total_principal_year = 0.0

    for _ in range(12):  # first year
        if outstanding <= 0:
            break

        interest_m = outstanding * r_month
        principal_m = emi - interest_m

        if principal_m > outstanding:
            principal_m = outstanding
            emi = interest_m + principal_m

        outstanding -= principal_m
        total_interest_year += interest_m
        total_principal_year += principal_m

    return emi, total_interest_year, total_principal_year, outstanding


# ---------- PAGE LAYOUT ----------
st.title("Working Capital Cycle ROI Calculator")
st.write(f"Logged in as **{userinfo['email']}**")


# ---------- INPUTS ----------
st.sidebar.header("Inputs")

starting_capital = st.sidebar.number_input(
    "Starting Capital",
    min_value=0.0,
    value=1_000_000.0,
    step=50_000.0,
)
sidebar_hint(in_words(starting_capital))

cycle_days = st.sidebar.number_input(
    "Cash Conversion Cycle (days)", min_value=1, value=45, step=1
)

margin_pct = st.sidebar.number_input(
    "Gross Margin on Sales (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5
)
margin = margin_pct / 100.0

fixed_cost_cycle = st.sidebar.number_input(
    "Fixed Operating Cost per Cycle", min_value=0.0, value=30000.0, step=5000.0
)
sidebar_hint(in_words(fixed_cost_cycle))

annual_fixed_cost = st.sidebar.number_input(
    "Annual Fixed Costs (Salaries, Rent, SG&A)",
    min_value=0.0,
    value=600000.0,
    step=10000.0,
)
sidebar_hint(in_words(annual_fixed_cost))

loan_amount = st.sidebar.number_input(
    "Loan Amount", min_value=0.0, value=500000.0, step=50000.0
)
sidebar_hint(in_words(loan_amount))

loan_interest_pct = st.sidebar.number_input(
    "Loan Interest Rate (%)", min_value=0.0, max_value=100.0, value=12.0, step=0.5
)
loan_interest_rate = loan_interest_pct / 100.0

loan_type = st.sidebar.radio(
    "Loan Type",
    ["Interest-only (CC/OD)", "EMI Monthly (Term Loan)"],
)

loan_tenure_months = 0
if loan_type == "EMI Monthly (Term Loan)":
    loan_tenure_months = st.sidebar.number_input(
        "Loan Tenure (months)", min_value=1, value=36, step=1
    )

tax_rate_pct = st.sidebar.number_input(
    "Tax Rate on Annual Profit (%)", min_value=0.0, max_value=100.0, value=30.0
)
tax_rate = tax_rate_pct / 100.0

round_cycles = st.sidebar.checkbox("Floor cycles (ignore partial last cycle)", value=True)


# ---------- CORE CALCULATION ----------
raw_cycles = 365 / cycle_days
cycles = math.floor(raw_cycles) if round_cycles else raw_cycles

if cycles <= 0:
    st.error("Cycle count is zero — adjust cycle days.")
    st.stop()

annual_fixed_per_cycle = annual_fixed_cost / cycles

# Margin on revenue → markup on cost
markup = margin / (1 - margin) if margin < 1 else 0

# Loan calculations
annual_loan_interest = 0
annual_principal_repayment = 0
loan_outstanding_end_year = loan_amount
emi_monthly = 0

if loan_amount > 0:

    if loan_type == "Interest-only (CC/OD)":
        annual_loan_interest = loan_amount * loan_interest_rate

    else:  # EMI
        emi_monthly, total_int, total_prin, outstanding_next = compute_emi_schedule_year(
            loan_amount, loan_interest_rate, loan_tenure_months
        )
        annual_loan_interest = total_int
        annual_principal_repayment = total_prin
        loan_outstanding_end_year = outstanding_next

loan_interest_cycle = annual_loan_interest / cycles
loan_principal_cycle = annual_principal_repayment / cycles

# Cycle simulation
capital = starting_capital
rows = []

for cycle in range(1, int(math.ceil(cycles)) + 1):

    cycle_fraction = 1.0
    if not round_cycles and cycle == math.ceil(cycles):
        cycle_fraction = cycles - math.floor(cycles)
        cycle_fraction = max(cycle_fraction, 1e-6)

    starting_cap = capital

    gross_profit = starting_cap * markup * cycle_fraction
    cost_fixed = fixed_cost_cycle * cycle_fraction
    cost_annual_alloc = annual_fixed_per_cycle * cycle_fraction
    cost_interest = loan_interest_cycle * cycle_fraction
    cost_principal = loan_principal_cycle * cycle_fraction

    net_profit = (
        gross_profit - cost_fixed - cost_annual_alloc - cost_interest - cost_principal
    )

    ending_cap = starting_cap + net_profit

    rows.append(
        {
            "Cycle": cycle,
            "Start Cap": starting_cap,
            "Gross Profit": gross_profit,
            "Fixed Cost": cost_fixed,
            "Annual Fixed Alloc": cost_annual_alloc,
            "Loan Interest": cost_interest,
            "Loan Principal": cost_principal,
            "Net Profit Before Tax": net_profit,
            "End Cap": ending_cap,
        }
    )

    capital = ending_cap

df = pd.DataFrame(rows)

ending_cap_before_tax = capital
cumulative_profit = ending_cap_before_tax - starting_capital

tax = cumulative_profit * tax_rate
net_income = cumulative_profit - tax
ending_cap_after_tax = starting_capital + net_income

roi_pct = (net_income / starting_capital) * 100


# ---------- OUTPUT ----------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Cycles per Year", f"{raw_cycles:.2f}")
col2.metric("Simulated Cycles", f"{cycles:.2f}")
col3.metric("Ending Capital (After Tax)", f"₹{ending_cap_after_tax:,.2f}")
col4.metric("ROI After Tax", f"{roi_pct:.2f}%")

st.write(f"Ending Capital in Words: **{in_words(ending_cap_after_tax)}**")
st.write(f"Annual Net Income: **₹{net_income:,.2f}** ({in_words(net_income)})")

st.markdown("---")
st.subheader("Loan Summary")
st.write(f"Annual Interest Paid: **₹{annual_loan_interest:,.2f}**")
st.write(f"Annual Principal Repaid: **₹{annual_principal_repayment:,.2f}**")
st.write(f"Outstanding Loan After 1 Year: **₹{loan_outstanding_end_year:,.2f}**")

if emi_monthly:
    st.write(f"Your EMI: **₹{emi_monthly:,.2f}/month**")

st.markdown("---")
st.subheader("Per-Cycle Breakdown")
st.dataframe(df, use_container_width=True)

st.subheader("Capital Growth")
st.line_chart(df.set_index("Cycle")["End Cap"])
