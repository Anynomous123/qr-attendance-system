# ============================================================
# QR SMART ATTENDANCE SYSTEM – FINAL INTEGRATED VERSION
# ============================================================

import streamlit as st
import sqlite3
import qrcode
import pandas as pd
import uuid
import io
import hashlib
import time
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from streamlit_javascript import st_javascript
from math import radians, sin, cos, sqrt, atan2
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import pagesizes

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(page_title="QR Attendance System", layout="wide")

ROTATION_SECONDS = 60
SECRET_KEY = "PHYSICS_DEPT_2026_SECURE"
APP_URL = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"

# ============================================================
# BEAUTIFUL UI STYLE
# ============================================================

st.markdown("""
<style>
.main {background-color:#f4fbf6;}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #198754, #0f5132);
}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown {
    color: white !important;
    font-weight: 600;
}
div.stButton > button {
    background: linear-gradient(90deg,#20c997,#198754);
    color:white;border-radius:10px;border:none;font-weight:600;
}
.metric-card {
    background:white;padding:20px;border-radius:15px;
    box-shadow:0 4px 15px rgba(0,0,0,0.08);
    text-align:center;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# TIME (IST)
# ============================================================

def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ============================================================
# DATABASE (NO SESSIONS TABLE)
# ============================================================

conn = sqlite3.connect("attendance.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    roll TEXT,
    name TEXT,
    class TEXT,
    gmail TEXT,
    mobile TEXT,
    subject TEXT,
    PRIMARY KEY (roll, subject)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    roll TEXT,
    name TEXT,
    subject TEXT,
    timestamp TEXT,
    PRIMARY KEY (roll, subject, timestamp)
)
""")

conn.commit()

# ============================================================
# ROTATING TOKEN GENERATOR
# ============================================================

def generate_rotating_token(subject, time_block=None):
    if time_block is None:
        time_block = int(time.time() // ROTATION_SECONDS)
    raw = f"{subject}-{time_block}-{SECRET_KEY}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ============================================================
# EMAIL FUNCTION
# ============================================================

def send_email(to_email, subject, body):
    try:
        sender = st.secrets["EMAIL_ADDRESS"]
        password = st.secrets["EMAIL_PASSWORD"]

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except:
        pass

# ============================================================
# FACULTY LOGIN
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.sidebar.subheader("Faculty Login")
    user = st.sidebar.text_input("Username")
    pwd = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        users = st.secrets["FACULTY_USERS"]
        if user in users and users[user] == pwd:
            st.session_state.logged_in = True
            st.session_state.faculty_name = user
            st.rerun()
        else:
            st.sidebar.error("Invalid Credentials")
    st.stop()

st.sidebar.success(f"Logged in as {st.session_state.faculty_name}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div style="background:linear-gradient(90deg,#0f5132,#198754);
padding:20px;border-radius:10px;color:white;">
<h2>G. B. Pant Memorial Govt. College – Department of Physics</h2>
<h4>QR Smart Attendance System</h4>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ============================================================
# TEACHER PANEL
# ============================================================

st.sidebar.markdown("## 🎓 Faculty Dashboard")

selected_class = st.sidebar.selectbox(
    "Select Class",
    ["B.Sc 1", "B.Sc 2", "B.Sc 3"]
)

subject = st.sidebar.text_input("Enter Subject Name")

if st.sidebar.button("Generate QR"):

    token = generate_rotating_token(subject)
    qr_data = f"{APP_URL}/?token={token}&subject={subject}"

    qr = qrcode.make(qr_data)
    buf = io.BytesIO()
    qr.save(buf)
    buf.seek(0)

    st.image(buf)
    st.success("🔄 Rotating QR Generated (Valid 60 seconds)")
    st.info("Refresh after 60 seconds for new QR")

# ============================================================
# ANALYTICS
# ============================================================

st.markdown("## 📊 Attendance Dashboard")

attendance_df = pd.read_sql_query(
    "SELECT * FROM attendance WHERE subject=?",
    conn,
    params=(subject,)
)

total_present = len(attendance_df)

total_sessions = pd.read_sql_query(
    """
    SELECT COUNT(DISTINCT DATE(timestamp)) as total
    FROM attendance
    WHERE subject=?
    """,
    conn,
    params=(subject,)
)["total"][0]

attendance_percent = 0
if total_sessions > 0:
    attendance_percent = round((total_present / total_sessions), 2)

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"<div class='metric-card'><h3>Total Present</h3><h1>{total_present}</h1></div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"<div class='metric-card'><h3>Total Class Days</h3><h1>{total_sessions}</h1></div>", unsafe_allow_html=True)

with col3:
    st.markdown(f"<div class='metric-card'><h3>Attendance Ratio</h3><h1>{attendance_percent}</h1></div>", unsafe_allow_html=True)

if not attendance_df.empty:

    st.dataframe(attendance_df, use_container_width=True)

    summary = attendance_df.groupby("roll").size().reset_index(name="Classes_Attended")
    summary["Attendance_%"] = round(summary["Classes_Attended"] / total_sessions * 100, 2)

    fig = px.bar(summary, x="roll", y="Attendance_%", color="Attendance_%",
                 color_continuous_scale="Greens")
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# STUDENT PORTAL
# ============================================================

st.divider()
st.markdown("## 🎓 Student Attendance Portal")

params = st.experimental_get_query_params()
token = params.get("token", [None])[0]
subject_db = params.get("subject", [None])[0]

if token and subject_db:

    current_block = int(time.time() // ROTATION_SECONDS)
    valid_now = generate_rotating_token(subject_db, current_block)
    valid_previous = generate_rotating_token(subject_db, current_block - 1)

    if token not in [valid_now, valid_previous]:
        st.error("⏰ QR Expired")
        st.stop()

    roll = st.text_input("Roll Number")

    if roll:
        today_date = now_ist().strftime("%Y-%m-%d")

        cursor.execute("""
            SELECT 1 FROM attendance
            WHERE roll=? AND subject=? AND DATE(timestamp)=?
        """, (roll, subject_db, today_date))

        if cursor.fetchone():
            st.warning("Attendance already marked today")
            st.stop()

        timestamp = now_ist().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            "INSERT INTO attendance VALUES (?, ?, ?, ?)",
            (roll, roll, subject_db, timestamp)
        )

        conn.commit()
        st.success("Attendance Marked Successfully")

st.markdown("""
<hr>
<center>© 2026 Physics Department | Smart Attendance Monitoring System</center>
""", unsafe_allow_html=True)
