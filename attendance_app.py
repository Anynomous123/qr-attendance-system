import streamlit as st
import sqlite3
import qrcode
import io
import hashlib
import time
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# ================== CONFIG ==================

ROTATION_SECONDS = 60
SECRET_KEY = "PHYSICS_DEPT_2026_SECURE"
APP_URL = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"

# ================== DATABASE ==================

conn = sqlite3.connect("attendance.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    roll TEXT,
    subject TEXT,
    timestamp TEXT,
    PRIMARY KEY (roll, subject, timestamp)
)
""")

conn.commit()

# ================== TOKEN GENERATOR ==================

def generate_rotating_token(subject, time_block=None):
    if time_block is None:
        time_block = int(time.time() // ROTATION_SECONDS)

    raw_string = f"{subject}-{time_block}-{SECRET_KEY}"
    return hashlib.sha256(raw_string.encode()).hexdigest()

# ================== UI ==================

st.title("📚 QR Attendance System")

menu = st.sidebar.selectbox("Select Mode", ["Teacher", "Student", "Analytics"])

# =====================================================
# ================== TEACHER SIDE =====================
# =====================================================

if menu == "Teacher":

    st.header("👨‍🏫 Teacher Panel")

    subject = st.text_input("Enter Subject Name")

    if st.button("Generate QR"):

        if not subject:
            st.warning("Please enter subject")
            st.stop()

        token = generate_rotating_token(subject)

        qr_data = f"{APP_URL}/?token={token}&subject={subject}"

        qr = qrcode.make(qr_data)
        buf = io.BytesIO()
        qr.save(buf)
        buf.seek(0)

        st.image(buf)
        st.success("🔄 QR Generated (Valid ~60 seconds)")
        st.info("Refresh after 60 seconds for new QR")

# =====================================================
# ================== STUDENT SIDE =====================
# =====================================================

if menu == "Student":

    st.header("🎓 Student Attendance")

    roll = st.text_input("Enter Roll Number")

    # Read token from URL
    params = st.experimental_get_query_params()
    token = params.get("token", [None])[0]
    subject_db = params.get("subject", [None])[0]

    if token and subject_db:

        if not roll:
            st.warning("Enter roll number")
            st.stop()

        # Validate token (current + previous block)
        current_block = int(time.time() // ROTATION_SECONDS)

        valid_now = generate_rotating_token(subject_db, current_block)
        valid_previous = generate_rotating_token(subject_db, current_block - 1)

        if token not in [valid_now, valid_previous]:
            st.error("⏰ QR Expired")
            st.stop()

        today_date = datetime.now().strftime("%Y-%m-%d")

        # Prevent duplicate attendance for same day
        cursor.execute("""
            SELECT 1 FROM attendance
            WHERE roll=? AND subject=? AND DATE(timestamp)=?
        """, (roll, subject_db, today_date))

        if cursor.fetchone():
            st.warning("⚠ Attendance already marked today!")
            st.stop()

        # Insert attendance
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO attendance (roll, subject, timestamp)
            VALUES (?, ?, ?)
        """, (roll, subject_db, timestamp))

        conn.commit()

        st.success("✅ Attendance Marked Successfully!")

    else:
        st.info("Scan QR Code to mark attendance.")

# =====================================================
# ================== ANALYTICS =====================
# =====================================================

if menu == "Analytics":

    st.header("📊 Attendance Analytics")

    subject = st.text_input("Enter Subject to View Analytics")

    if subject:

        attendance_df = pd.read_sql_query(
            "SELECT * FROM attendance WHERE subject=?",
            conn,
            params=(subject,)
        )

        if attendance_df.empty:
            st.warning("No attendance data found.")
            st.stop()

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
            attendance_percent = round(
                (total_present / total_sessions), 2
            )

        st.metric("Total Attendance Records", total_present)
        st.metric("Total Class Days", total_sessions)

        st.subheader("Attendance Records")
        st.dataframe(attendance_df)

        # Download CSV
        csv = attendance_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download CSV",
            csv,
            "attendance.csv",
            "text/csv"
        )
