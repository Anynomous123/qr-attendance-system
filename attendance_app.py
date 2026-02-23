import streamlit as st
import qrcode
import sqlite3
import pandas as pd
import uuid
import io
from datetime import datetime, timedelta

# -------------------------
# DATABASE SETUP
# -------------------------

conn = sqlite3.connect("attendance.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS attendance
             (roll TEXT, name TEXT, subject TEXT,
              timestamp TEXT, token TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS sessions
             (token TEXT, subject TEXT, expiry TEXT)''')

# NEW: session count table
c.execute('''CREATE TABLE IF NOT EXISTS session_count
             (subject TEXT, date TEXT)''')

conn.commit()

# -------------------------
# AUTO CLEAN EXPIRED SESSIONS
# -------------------------

current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
c.execute("DELETE FROM sessions WHERE expiry < ?", (current_time,))
conn.commit()

# -------------------------
# FACULTY LOGIN SYSTEM
# -------------------------

def login():
    st.sidebar.subheader("Faculty Login")

    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        faculty_users = st.secrets["FACULTY_USERS"]

        if username in faculty_users and faculty_users[username] == password:
            st.session_state["logged_in"] = True
            st.session_state["faculty_name"] = username
            st.sidebar.success("Login Successful")
        else:
            st.sidebar.error("Invalid Credentials")


def logout():
    st.session_state["logged_in"] = False
    st.sidebar.success("Logged out")


if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    st.sidebar.write(f"Logged in as: {st.session_state['faculty_name']}")
    if st.sidebar.button("Logout"):
        logout()

# -------------------------
# MAIN TITLE
# -------------------------

st.title("📚 QR Based Attendance System – Physics Department")

# ============================================================
# =================== TEACHER DASHBOARD ======================
# ============================================================

if st.session_state["logged_in"]:

    st.sidebar.header("Teacher Panel")

    subjects = [
        "Classical Mechanics",
        "Quantum Mechanics",
        "Electrodynamics",
        "Mathematical Physics",
        "Nuclear Physics",
        "Solid State Physics"
    ]

    subject = st.sidebar.selectbox("Select Subject", subjects)

    duration = st.sidebar.number_input(
        "QR Valid Duration (minutes)",
        min_value=1,
        max_value=60,
        value=5
    )

    st.header("Faculty Dashboard")

    if st.sidebar.button("Generate QR"):

        token = str(uuid.uuid4())
        expiry = datetime.now() + timedelta(minutes=duration)

        c.execute("INSERT INTO sessions VALUES (?,?,?)",
                  (token, subject,
                   expiry.strftime("%Y-%m-%d %H:%M:%S")))

        # NEW: Track session count
        c.execute("INSERT INTO session_count VALUES (?, ?)",
                  (subject, datetime.now().strftime("%Y-%m-%d")))

        conn.commit()

        app_url = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"
        qr_data = f"{app_url}/?token={token}"

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        st.image(buf, caption="Scan to Mark Attendance")

    # -------- Live Attendance --------

    st.subheader("Live Attendance Record")

    df = pd.read_sql_query("SELECT * FROM attendance", conn)
    st.dataframe(df)

    # -------- Attendance Percentage --------

    st.subheader("Attendance Percentage Summary")

    if not df.empty:

        sessions_df = pd.read_sql_query("SELECT * FROM session_count", conn)

        if not sessions_df.empty:

            total_sessions = (
                sessions_df.groupby("subject")
                .size()
                .reset_index(name="Total_Classes")
            )

            attendance_count = (
                df.groupby(["roll", "subject"])
                .size()
                .reset_index(name="Classes_Attended")
            )

            merged = attendance_count.merge(total_sessions, on="subject")

            merged["Attendance_%"] = (
                merged["Classes_Attended"] /
                merged["Total_Classes"] * 100
            ).round(2)

            st.dataframe(merged)

        else:
            st.info("No sessions conducted yet.")

    # -------- Download --------

    st.subheader("Download Attendance")

    if not df.empty:
        csv_data = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Attendance CSV",
            data=csv_data,
            file_name="attendance.csv",
            mime="text/csv",
        )
    else:
        st.info("No attendance records yet.")

# ============================================================
# =================== STUDENT SECTION ========================
# ============================================================

st.divider()
st.header("Student Attendance")

query_params = st.query_params
token_from_url = query_params.get("token")

if token_from_url:

    c.execute("SELECT subject, expiry FROM sessions WHERE token=?",
              (token_from_url,))
    session = c.fetchone()

    if session:

        subject_db, expiry_db = session
        expiry_time = datetime.strptime(expiry_db, "%Y-%m-%d %H:%M:%S")

        if datetime.now() <= expiry_time:

            st.subheader(f"Subject: {subject_db}")

            roll = st.text_input("Roll Number")
            name = st.text_input("Name")

            if st.button("Submit Attendance"):

                c.execute("SELECT * FROM attendance WHERE roll=? AND token=?",
                          (roll, token_from_url))

                if c.fetchone():
                    st.warning("Attendance already marked!")
                else:
                    c.execute("INSERT INTO attendance VALUES (?,?,?,?,?)",
                              (roll, name,
                               subject_db,
                               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               token_from_url))
                    conn.commit()
                    st.success("Attendance Marked Successfully!")

        else:
            st.error("QR Expired!")

    else:
        st.error("Invalid QR!")
else:
    st.info("Please scan a valid QR code to mark attendance.")
