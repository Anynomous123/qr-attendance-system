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

#conn = sqlite3.connect("attendance.db", check_same_thread=False, timeout=10)
conn = sqlite3.connect(
	"attendance.db",
	check_same_thread=False,
	timeout=30,
	isolation_level=None
)


cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")
#cursor = conn.cursor()

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
        "Electricity, Magnetism & EMT (PHYS102TH)",
        "Statistical & Thermal Physics (PHYS201TH)",
        "Waves and Optics (PHYS202TH)",
        "Computational Physics (PHYS204TH)",
        "Electronic Circuits & Metwork Skills (PHYS205TH)",
        "Modern Physics (PHYS301TH)",
        "Nuclear and Particle Physics (PHYS304TH)",
        "Radiation Safety (PHYS307TH)",
        "Renewable Energy and Energy Harvesting (PHYS310TH)",
        "Mechanics (PHYS101PR)",
        "Electricity, Magnetism & EMT (PHYS102PR)",
        "Statistical & Thermal Physics (PHYS201PR)",
        "Waves and Optics (PHYS202PR)", 
        "Computational Physics (PHYS204SE)", 
        "Electronic Circuits & Metwork Skills (PHYS205SE)",   
        "Modern Physics (PHYS301PR)", 
        "Nuclear and Particle Physics (PHYS304TU)",  
        "Radiation Safety (PHYS307SE)",
        "Renewable Energy and Energy Harvesting (PHYS310TH)"
    ]

    selected_class = st.sidebar.selectbox(
		"Select Class",
		["B.Sc 1", "B.Sc 2", "B.Sc 3"]
	)
	
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
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚠ Admin Controls")
        admin_password = st.sidebar.text_input("Admin Reset Password", type="password")
        if st.sidebar.button("Reset Attendance Data"):
            if admin_password == st.secrets["ADMIN_RESET_KEY"]:
                cursor.execute("DELETE FROM attendance")
                cursor.execute("DELETE FROM sessions")
                conn.commit()
                st.sidebar.success("Attendance Data Reset Successfully")
            else:
                st.sidebar.error("Incorrect Admin Password")

    # ================= ANALYTICS =================

    #attendance_df = pd.read_sql_query("SELECT * FROM attendance", conn)
    attendance_df = pd.read_sql_query(
        "SELECT * FROM attendance WHERE subject=?",
	conn,
	params=(subject,)
    )
    st.subheader("📋 Live Attendance Record")
    st.dataframe(attendance_df, use_container_width=True)
    if st.button("Show All Subjects Data"):
        all_data = pd.read_sql_query("SELECT * FROM attendance", conn)
        st.dataframe(all_data, use_container_width=True)

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

        #fig = px.bar(merged, x="roll", y="Attendance_%", color="subject")
        #st.plotly_chart(fig, use_container_width=True)
        
        fig1 = px.bar(total_sessions, x="subject", y="Total_Classes")
        st.plotly_chart(fig1, use_container_width=True)
        
        fig2 = px.bar(merged, x="roll", y="Attendance_%", color="subject")
        st.plotly_chart(fig2, use_container_width=True)

        attendance_df["timestamp"] = pd.to_datetime(attendance_df["timestamp"])
        attendance_df["date"] = attendance_df["timestamp"].dt.date
        daily = attendance_df.groupby("date").size().reset_index(name="Total")

        fig3 = px.line(daily, x="date", y="Total", markers=True)
        st.plotly_chart(fig3, use_container_width=True)

        low = merged[merged["Attendance_%"] < 75]
        st.subheader("⚠ Below 75% Attendance")
        st.dataframe(low)

        # CSV DOWNLOAD
        #csv_data = attendance_df.to_csv(index=False).encode("utf-8")
        #st.download_button("Download attendance.csv", csv_data, "attendance.csv", "text/csv")
        # Export Current Subject
        csv_subject = attendance_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Current Subject CSV",
            csv_subject,
	    f"{subject}_attendance.csv",
	    "text/csv"
        )
        # Export All Subjects
        all_data = pd.read_sql_query("SELECT * FROM attendance", conn)
        csv_all = all_data.to_csv(index=False).encode("utf-8")
        st.download_button(
	    "Download All Subjects CSV",
	    csv_all,
	    "all_attendance.csv",
	    "text/csv"
	)
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
            # Live student counter
            cursor.execute(
                "SELECT COUNT(*) FROM attendance WHERE token=?",
        	 (token,)
	    )
	    count = cursor.fetchone()[0]


	    st.info(f"👥 Students Marked: {count}")


	# Auto close after 100 students
	    if count >= 100:
		st.error("Attendance Closed: 100 Students Reached")
		st.stop()
        #if now_ist() <= expiry:
         #   cursor.execute(
          #      "SELECT COUNT(*) FROM attendance WHERE token=?",
           #     (token,)
            #)
	    #count = cursor.fetchone()[0]
	    
	    #st.info(f"👥 Students Marked: {count}")
	    
	    #if count >= 100:
	     #   st.error("Attendance Closed: 100 Students Reached")
	      #  st.stop()
	            
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
