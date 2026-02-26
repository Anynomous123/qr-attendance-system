import streamlit as st
import qrcode
import pandas as pd
import uuid
import io
from datetime import datetime, timedelta
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
import sqlite3

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(page_title="QR Attendance System", layout="wide")

# ============================================================
# IST TIME FUNCTION
# ============================================================

def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ============================================================
# SQLITE DATABASE (HIGH SPEED – NO CRASH)
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
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    subject TEXT,
    expiry TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    roll TEXT,
    name TEXT,
    subject TEXT,
    timestamp TEXT,
    token TEXT,
    PRIMARY KEY (roll, token)
)
""")

conn.commit()

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
    st.session_state["logged_in"] = False

def login():
    st.sidebar.subheader("Faculty Login")
    user = st.sidebar.text_input("Username")
    pwd = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        users = st.secrets["FACULTY_USERS"]
        if user in users and users[user] == pwd:
            st.session_state["logged_in"] = True
            st.session_state["faculty_name"] = user
            st.sidebar.success("Login Successful")
        else:
            st.sidebar.error("Invalid Credentials")

if not st.session_state["logged_in"]:
    login()
else:
    st.sidebar.success(f"Logged in as {st.session_state['faculty_name']}")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False

# ============================================================
# TITLE
# ============================================================

st.title("📚 QR Based Attendance System – Physics Department")

# ============================================================
# TEACHER DASHBOARD
# ============================================================

if st.session_state["logged_in"]:

    st.sidebar.header("Teacher Panel")

    subjects = [
        "Mechanics (PHYS101TH)",
        "Modern Physics (PHYS301TH)",
        "Nuclear and Particle Physics (PHYS304TH)"
    ]

    subject = st.sidebar.selectbox("Select Subject", subjects)
    duration = st.sidebar.number_input("QR Valid Duration (minutes)", 1, 60, 5)

    if st.sidebar.button("Generate QR"):

        token = str(uuid.uuid4())
        expiry = now_ist() + timedelta(minutes=duration)

        cursor.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            (token, subject, expiry.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()

        app_url = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"
        qr_data = f"{app_url}/?token={token}"

        qr = qrcode.make(qr_data)
        buf = io.BytesIO()
        qr.save(buf)
        buf.seek(0)
        st.image(buf)

    # ================= ANALYTICS =================

    attendance_df = pd.read_sql_query("SELECT * FROM attendance", conn)

    st.subheader("📋 Live Attendance Record")
    st.dataframe(attendance_df, use_container_width=True)

    if not attendance_df.empty:

        total_sessions = pd.read_sql_query(
            "SELECT subject, COUNT(*) as Total_Classes FROM sessions GROUP BY subject",
            conn
        )

        attendance_count = attendance_df.groupby(["roll","subject"]).size().reset_index(name="Classes_Attended")

        merged = attendance_count.merge(total_sessions, on="subject")
        merged["Attendance_%"] = (merged["Classes_Attended"] / merged["Total_Classes"] * 100).round(2)

        st.subheader("📊 Attendance % Summary")
        st.dataframe(merged, use_container_width=True)

        fig = px.bar(merged, x="roll", y="Attendance_%", color="subject")
        st.plotly_chart(fig, use_container_width=True)

        # CSV DOWNLOAD
        csv_data = attendance_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download attendance.csv", csv_data, "attendance.csv", "text/csv")

# ============================================================
# STUDENT SECTION
# ============================================================

st.divider()
st.header("Student Attendance")

query = st.experimental_get_query_params()
token = query.get("token", [None])[0]

if token:

    cursor.execute("SELECT * FROM sessions WHERE token=?", (token,))
    session = cursor.fetchone()

    if session:

        subject_db = session[1]
        expiry = datetime.strptime(session[2], "%Y-%m-%d %H:%M:%S")

        if now_ist() <= expiry:

            roll = st.text_input("Roll Number")

            if roll:

                cursor.execute(
                    "SELECT * FROM students WHERE roll=? AND subject=?",
                    (roll, subject_db)
                )
                registered = cursor.fetchone()

                # ================= FIRST TIME =================
                if not registered:

                    st.subheader("New Registration")

                    name = st.text_input("Full Name")
                    student_class = st.selectbox("Class", ["B.Sc 1", "B.Sc 2", "B.Sc 3"])
                    gmail = st.text_input("Gmail Address")
                    mobile = st.text_input("Mobile Number")

                    if st.button("Register & Mark Attendance"):

                        try:
                            cursor.execute(
                                "INSERT INTO students VALUES (?, ?, ?, ?, ?, ?)",
                                (roll, name, student_class, gmail, mobile, subject_db)
                            )

                            cursor.execute(
                                "INSERT INTO attendance VALUES (?, ?, ?, ?, ?)",
                                (
                                    roll,
                                    name,
                                    subject_db,
                                    now_ist().strftime("%Y-%m-%d %H:%M:%S"),
                                    token
                                )
                            )

                            conn.commit()

                            send_email(gmail, "Attendance Confirmed",
                                       f"Dear {name}, your attendance is marked.")

                            st.success("Registered & Attendance Marked")

                        except sqlite3.IntegrityError:
                            st.warning("Already registered or attendance marked.")

                # ================= ALREADY REGISTERED =================
                else:

                    name = registered[1]
                    gmail = registered[3]

                    cursor.execute(
                        "SELECT * FROM attendance WHERE roll=? AND token=?",
                        (roll, token)
                    )

                    if cursor.fetchone():
                        st.warning("Attendance already marked.")
                    else:

                        if st.button("Mark Attendance"):

                            try:
                                cursor.execute(
                                    "INSERT INTO attendance VALUES (?, ?, ?, ?, ?)",
                                    (
                                        roll,
                                        name,
                                        subject_db,
                                        now_ist().strftime("%Y-%m-%d %H:%M:%S"),
                                        token
                                    )
                                )

                                conn.commit()

                                send_email(gmail, "Attendance Confirmed",
                                           f"Dear {name}, your attendance is marked.")

                                st.success("Attendance Marked Successfully")

                            except sqlite3.IntegrityError:
                                st.warning("Attendance already marked.")

        else:
            st.error("QR Expired.")

    else:
        st.error("Invalid QR Code.")
