import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Contract Risk Analyzer",
    page_icon="⚖️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Reset & base ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #0a0e1a !important;
    color: #e8e6e1 !important;
    font-family: 'DM Sans', sans-serif !important;
}

[data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at 20% 10%, #111827 0%, #0a0e1a 60%) !important;
}

/* ── Hide streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebar"] { display: none; }
[data-testid="collapsedControl"] { display: none; }

/* ── Main container ── */
.main .block-container {
    max-width: 780px !important;
    padding: 3rem 2rem !important;
}

/* ── Typography ── */
h1, h2, h3 {
    font-family: 'DM Serif Display', serif !important;
    letter-spacing: -0.02em;
}

/* ── Logo / hero ── */
.hero {
    text-align: center;
    padding: 2.5rem 0 2rem;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    margin-bottom: 2.5rem;
}
.hero-icon {
    font-size: 2.8rem;
    margin-bottom: 0.5rem;
    display: block;
}
.hero-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.4rem;
    color: #f0ede8;
    margin: 0;
    line-height: 1.1;
}
.hero-subtitle {
    color: #6b7280;
    font-size: 0.9rem;
    margin-top: 0.4rem;
    font-weight: 300;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── Auth tabs ── */
.auth-tabs {
    display: flex;
    gap: 0;
    margin-bottom: 2rem;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    overflow: hidden;
    background: rgba(255,255,255,0.03);
}
.auth-tab {
    flex: 1;
    padding: 0.75rem;
    text-align: center;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: #6b7280;
    border: none;
    background: transparent;
    transition: all 0.2s;
}
.auth-tab.active {
    background: rgba(251, 191, 36, 0.12);
    color: #fbbf24;
    border-bottom: 2px solid #fbbf24;
}

/* ── Cards ── */
.card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 2rem;
    margin-bottom: 1.5rem;
    backdrop-filter: blur(10px);
}

/* ── Input fields ── */
[data-testid="stTextInput"] input,
[data-testid="stTextInput"] input:focus {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    border-radius: 8px !important;
    color: #f0ede8 !important;
    font-family: 'DM Sans', sans-serif !important;
    padding: 0.65rem 1rem !important;
    transition: border 0.2s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: rgba(251,191,36,0.5) !important;
    box-shadow: 0 0 0 3px rgba(251,191,36,0.08) !important;
}
[data-testid="stTextInput"] label {
    color: #9ca3af !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}

/* ── Buttons ── */
[data-testid="stButton"] button {
    background: #fbbf24 !important;
    color: #0a0e1a !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    padding: 0.65rem 1.5rem !important;
    transition: all 0.2s !important;
    width: 100% !important;
}
[data-testid="stButton"] button:hover {
    background: #f59e0b !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(251,191,36,0.25) !important;
}

/* Secondary button (logout, nav) */
.btn-secondary > [data-testid="stButton"] button {
    background: rgba(255,255,255,0.06) !important;
    color: #9ca3af !important;
    width: auto !important;
}
.btn-secondary > [data-testid="stButton"] button:hover {
    background: rgba(255,255,255,0.1) !important;
    color: #e8e6e1 !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 2px dashed rgba(255,255,255,0.1) !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.02) !important;
    padding: 1rem !important;
    transition: border-color 0.2s !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: rgba(251,191,36,0.3) !important;
}
[data-testid="stFileUploader"] label {
    color: #6b7280 !important;
}

/* ── Risk cards ── */
.risk-card {
    border-radius: 10px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 0.75rem;
    border-left: 3px solid;
    background: rgba(255,255,255,0.03);
    transition: background 0.2s;
}
.risk-card:hover { background: rgba(255,255,255,0.06); }
.risk-high  { border-color: #ef4444; }
.risk-med   { border-color: #fbbf24; }
.risk-low   { border-color: #34d399; }

.risk-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.risk-type {
    font-weight: 600;
    font-size: 0.9rem;
    color: #f0ede8;
}
.badge {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.badge-high { background: rgba(239,68,68,0.15); color: #f87171; }
.badge-med  { background: rgba(251,191,36,0.15); color: #fbbf24; }
.badge-low  { background: rgba(52,211,153,0.15); color: #34d399; }

.risk-text {
    font-size: 0.85rem;
    color: #9ca3af;
    line-height: 1.6;
    font-style: italic;
    border-left: 1px solid rgba(255,255,255,0.08);
    padding-left: 0.9rem;
    margin-top: 0.4rem;
}
.confidence-bar-bg {
    background: rgba(255,255,255,0.06);
    border-radius: 4px;
    height: 4px;
    margin-top: 0.6rem;
    overflow: hidden;
}
.confidence-bar { height: 4px; border-radius: 4px; }

/* ── Navbar ── */
.navbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.2rem;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
    margin-bottom: 2rem;
}
.nav-brand {
    font-family: 'DM Serif Display', serif;
    font-size: 1.1rem;
    color: #fbbf24;
}
.nav-user {
    font-size: 0.8rem;
    color: #6b7280;
}
.nav-links {
    display: flex;
    gap: 0.5rem;
}

/* ── Stats row ── */
.stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.stat-box {
    flex: 1;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 1rem;
    text-align: center;
}
.stat-num {
    font-family: 'DM Serif Display', serif;
    font-size: 2rem;
    color: #fbbf24;
    line-height: 1;
}
.stat-label {
    font-size: 0.72rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 0.3rem;
}

/* ── History table ── */
.history-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.9rem 1.1rem;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 0.85rem;
}
.history-row:last-child { border-bottom: none; }
.history-file { color: #e8e6e1; font-weight: 500; }
.history-meta { color: #6b7280; font-size: 0.78rem; margin-top: 0.1rem; }
.history-risks {
    background: rgba(251,191,36,0.1);
    color: #fbbf24;
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    border: none !important;
    font-size: 0.85rem !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #fbbf24 !important; }

/* ── Download button ── */
[data-testid="stDownloadButton"] button {
    background: rgba(52,211,153,0.12) !important;
    color: #34d399 !important;
    border: 1px solid rgba(52,211,153,0.25) !important;
    width: auto !important;
}
[data-testid="stDownloadButton"] button:hover {
    background: rgba(52,211,153,0.2) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* ── Divider ── */
hr { border-color: rgba(255,255,255,0.06) !important; }

/* ── Section heading ── */
.section-label {
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #4b5563;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_auth_header():
    return {"Authorization": f"Bearer {st.session_state['token']}"}


def is_logged_in():
    return st.session_state.get("token") is not None


def logout():
    st.session_state.clear()
    st.rerun()


def risk_meta(confidence: float):
    """Return (level_label, css_class, badge_class, bar_color) from confidence."""
    if confidence >= 0.75:
        return "High Risk", "risk-high", "badge-high", "#ef4444"
    elif confidence >= 0.50:
        return "Medium Risk", "risk-med", "badge-med", "#fbbf24"
    else:
        return "Low Risk", "risk-low", "badge-low", "#34d399"


# ── Hero header (always shown) ─────────────────────────────────────────────────

st.markdown("""
<div class="hero">
    <span class="hero-icon">⚖️</span>
    <h1 class="hero-title">Contract Risk Analyzer</h1>
    <p class="hero-subtitle">AI-powered legal document analysis</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH PAGES
# ══════════════════════════════════════════════════════════════════════════════

def auth_pages():
    # Tab state
    if "auth_tab" not in st.session_state:
        st.session_state["auth_tab"] = "login"

    col_login, col_signup = st.columns(2)
    with col_login:
        if st.button("Login", key="tab_login"):
            st.session_state["auth_tab"] = "login"
            st.rerun()
    with col_signup:
        if st.button("Create Account", key="tab_signup"):
            st.session_state["auth_tab"] = "signup"
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    if st.session_state["auth_tab"] == "login":
        login_form()
    else:
        signup_form()


def login_form():
    st.markdown("<p class='section-label'>Sign in to your account</p>", unsafe_allow_html=True)

    username = st.text_input("Username", placeholder="your username", key="login_username")
    password = st.text_input("Password", type="password", placeholder="••••••••", key="login_password")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Sign In →", key="login_btn"):
        if not username or not password:
            st.error("Please fill in both fields.")
            return
        try:
            resp = requests.post(
                f"{API_URL}/login",
                json={"username": username, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state["token"] = data["access_token"]
                st.session_state["username"] = username
                st.session_state["page"] = "analyze"
                st.rerun()
            elif resp.status_code == 401:
                st.error("Invalid username or password.")
            else:
                st.error(resp.json().get("detail", "Login failed."))
        except requests.ConnectionError:
            st.error("Cannot connect to server. Make sure your API is running.")
        except requests.Timeout:
            st.error("Request timed out. Try again.")


def signup_form():
    st.markdown("<p class='section-label'>Create a new account</p>", unsafe_allow_html=True)

    username = st.text_input("Username", placeholder="choose a username", key="signup_username")
    password = st.text_input("Password", type="password", placeholder="••••••••", key="signup_password")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Create Account →", key="signup_btn"):
        if not username or not password:
            st.error("Please fill in both fields.")
            return
        try:
            resp = requests.post(
                f"{API_URL}/signup/",
                json={"username": username, "password": password},
                timeout=10,
            )
            if resp.status_code == 200:
                st.success("Account created! You can now sign in.")
                st.session_state["auth_tab"] = "login"
                st.rerun()
            elif resp.status_code == 400:
                st.error(resp.json().get("detail", "Username already taken."))
            else:
                st.error(resp.json().get("detail", "Signup failed."))
        except requests.ConnectionError:
            st.error("Cannot connect to server. Make sure your API is running.")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APP (logged in)
# ══════════════════════════════════════════════════════════════════════════════

def navbar():
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        st.markdown(
            f"<div style='padding:0.4rem 0; color:#6b7280; font-size:0.82rem;'>"
            f"Signed in as <span style='color:#fbbf24; font-weight:600;'>"
            f"{st.session_state.get('username', '')}</span></div>",
            unsafe_allow_html=True
        )
    with col2:
        if st.button("Analyze", key="nav_analyze"):
            st.session_state["page"] = "analyze"
            st.rerun()
    with col3:
        if st.button("History", key="nav_history"):
            st.session_state["page"] = "history"
            st.rerun()
    with col4:
        if st.button("Logout", key="nav_logout"):
            logout()
    st.markdown("<hr>", unsafe_allow_html=True)


def analyze_page():
    st.markdown("<p class='section-label'>Upload a contract PDF</p>", unsafe_allow_html=True)

    uploaded_file = st.file_uploader(
        "Drop your PDF here or click to browse",
        type=["pdf"],
        label_visibility="collapsed",
    )

    if uploaded_file:
        st.markdown(
            f"<div style='font-size:0.82rem; color:#6b7280; margin:0.5rem 0;'>"
            f"📄 {uploaded_file.name} · {uploaded_file.size / 1024:.1f} KB</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Analyze Contract →", key="analyze_btn"):
        if not uploaded_file:
            st.error("Please upload a PDF first.")
            return

        with st.spinner("Analyzing contract... this may take a moment."):
            try:
                resp = requests.post(
                    f"{API_URL}/analyze/",
                    headers=get_auth_header(),
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                    timeout=120,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state["last_result"] = data
                elif resp.status_code == 401:
                    st.error("Session expired. Please log in again.")
                    logout()
                elif resp.status_code == 413:
                    st.error("File too large. Maximum size is 10 MB.")
                elif resp.status_code == 400:
                    st.error(resp.json().get("detail", "Invalid file."))
                else:
                    st.error(resp.json().get("detail", "Analysis failed. Try again."))

            except requests.ConnectionError:
                st.error("Cannot connect to server.")
            except requests.Timeout:
                st.error("Analysis timed out. Try a shorter document.")

    # ── Results ──
    result = st.session_state.get("last_result")
    if not result:
        return

    risks = result.get("risks", [])
    total = result.get("total_risks", 0)

    high = sum(1 for r in risks if r.get("confidence", 0) >= 0.75)
    medium = sum(1 for r in risks if 0.50 <= r.get("confidence", 0) < 0.75)
    low = sum(1 for r in risks if r.get("confidence", 0) < 0.50)

    # Stats row
    st.markdown(f"""
    <div class="stats-row">
        <div class="stat-box">
            <div class="stat-num">{total}</div>
            <div class="stat-label">Total Risks</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#ef4444">{high}</div>
            <div class="stat-label">High Risk</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#fbbf24">{medium}</div>
            <div class="stat-label">Medium Risk</div>
        </div>
        <div class="stat-box">
            <div class="stat-num" style="color:#34d399">{low}</div>
            <div class="stat-label">Low Risk</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<p class='section-label'>Identified risks</p>", unsafe_allow_html=True)

    for i, risk in enumerate(risks, start=1):
        confidence = risk.get("confidence", 0)
        risk_type = risk.get("type", "Unknown")
        snippet = risk.get("text_snippet", "")
        level, card_cls, badge_cls, bar_color = risk_meta(confidence)
        pct = int(confidence * 100)

        st.markdown(f"""
        <div class="risk-card {card_cls}">
            <div class="risk-header">
                <span class="risk-type">{i}. {risk_type}</span>
                <span class="badge {badge_cls}">{level}</span>
            </div>
            <div class="risk-text">"{snippet}"</div>
            <div class="confidence-bar-bg">
                <div class="confidence-bar" style="width:{pct}%; background:{bar_color};"></div>
            </div>
            <div style="font-size:0.72rem; color:#4b5563; margin-top:0.3rem;">
                Confidence: {pct}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Download
    download_url = result.get("download_url")
    if download_url:
        st.markdown("<br>", unsafe_allow_html=True)
        try:
            pdf_resp = requests.get(
                f"{API_URL}{download_url}",
                headers=get_auth_header(),
                timeout=30,
            )
            if pdf_resp.status_code == 200:
                filename = download_url.split("/")[-1]
                st.download_button(
                    label="⬇ Download Analyzed PDF",
                    data=pdf_resp.content,
                    file_name=filename,
                    mime="application/pdf",
                )
        except requests.ConnectionError:
            st.warning("Could not fetch download link.")


def history_page():
    st.markdown("<p class='section-label'>Your past analyses</p>", unsafe_allow_html=True)

    try:
        resp = requests.get(
            f"{API_URL}/history/",
            headers=get_auth_header(),
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            history = data.get("history", [])

            if not history:
                st.info("No analyses yet. Upload a contract to get started.")
                return

            st.markdown(
                f"<p style='color:#6b7280; font-size:0.85rem; margin-bottom:1.2rem;'>"
                f"{data['total_searches']} document(s) analyzed</p>",
                unsafe_allow_html=True,
            )

            rows_html = ""
            for entry in history:
                fname = entry.get("filename", "Unknown")
                num_risks = entry.get("risks", 0)
                timestamp = entry.get("timestamp", "")
                if timestamp and "T" in str(timestamp):
                    timestamp = str(timestamp).split("T")[0]

                rows_html += f"""
                <div class="history-row">
                    <div>
                        <div class="history-file">📄 {fname}</div>
                        <div class="history-meta">{timestamp}</div>
                    </div>
                    <span class="history-risks">{num_risks} risks</span>
                </div>
                """

            st.markdown(
                f"<div class='card' style='padding:0;'>{rows_html}</div>",
                unsafe_allow_html=True,
            )

        elif resp.status_code == 401:
            st.error("Session expired. Please log in again.")
            logout()
        else:
            st.error(resp.json().get("detail", "Failed to load history."))

    except requests.ConnectionError:
        st.error("Cannot connect to server.")


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════════════════════════════════════════

if not is_logged_in():
    auth_pages()
else:
    if "page" not in st.session_state:
        st.session_state["page"] = "analyze"

    navbar()

    if st.session_state["page"] == "analyze":
        analyze_page()
    else:
        history_page()
