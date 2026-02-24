import streamlit as st
import qrcode
import pandas as pd
import uuid
import io
from datetime import datetime, timedelta
import plotly.express as px
import smtplib
from email.mime.text import MIMEText

import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="QR Attendance System", layout="wide")

# ============================================================
# GOOGLE SHEETS SETUP
# ============================================================

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)
sheet = client.open("Physics_Attendance_DB")

attendance_sheet = sheet.worksheet("attendance")
sessions_sheet = sheet.worksheet("sessions")
session_count_sheet = sheet.worksheet("session_count")
students_sheet = sheet.worksheet("students")

# ============================================================
# SAFE LOADER
# ============================================================

def load_sheet_safe(worksheet, required_columns):
    data = worksheet.get_all_records()
    if data:
        return pd.DataFrame(data)
    return pd.DataFrame(columns=required_columns)

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
# MAIN TITLE
# ============================================================

st.title("📚 QR Based Attendance System – Physics Department")

# ============================================================
# TEACHER DASHBOARD + ANALYTICS
# ============================================================

if st.session_state["logged_in"]:

    st.sidebar.header("Teacher Panel")

    subjects = [
        "Classical Mechanics",
        "Quantum Mechanics",
        "Electrodynamics",
        "Mathematical Physics",
        "Nuclear Physics",
        "Solid State Physics",
        "QFT"
    ]

    subject = st.sidebar.selectbox("Select Subject", subjects)
    duration = st.sidebar.number_input("QR Valid Duration (minutes)", 1, 60, 5)

    if st.sidebar.button("Generate QR"):

        token = str(uuid.uuid4())
        expiry = datetime.now() + timedelta(minutes=duration)

        sessions_sheet.append_row([
            token,
            subject,
            expiry.strftime("%Y-%m-%d %H:%M:%S")
        ])

        session_count_sheet.append_row([
            subject,
            datetime.now().strftime("%Y-%m-%d")
        ])

        app_url = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"
        qr_data = f"{app_url}/?token={token}"

        qr = qrcode.make(qr_data)
        buf = io.BytesIO()
        qr.save(buf)
        buf.seek(0)
        st.image(buf)

    # ================= ANALYTICS =================

    attendance_df = load_sheet_safe(
        attendance_sheet,
        ["roll", "name", "subject", "timestamp", "token"]
    )

    session_df = load_sheet_safe(
        session_count_sheet,
        ["subject", "date"]
    )

    st.subheader("📋 Live Attendance Record")
    st.dataframe(attendance_df, use_container_width=True)

    if not attendance_df.empty and not session_df.empty:

        total_sessions = session_df.groupby("subject").size().reset_index(name="Total_Classes")
        attendance_count = attendance_df.groupby(["roll","subject"]).size().reset_index(name="Classes_Attended")

        merged = attendance_count.merge(total_sessions, on="subject")
        merged["Attendance_%"] = (merged["Classes_Attended"] / merged["Total_Classes"] * 100).round(2)

        st.subheader("📊 Attendance Percentage Summary")
        st.dataframe(merged, use_container_width=True)

        st.header("📈 Analytics Dashboard")

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

        # ================= CSV DOWNLOAD =================
        st.subheader("⬇ Download Attendance Data")
        csv_data = attendance_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download attendance.csv",
            data=csv_data,
            file_name="attendance.csv",
            mime="text/csv"
        )

# ============================================================
# STUDENT SECTION (ULTRA STRICT CONTROL)
# ============================================================

st.divider()
st.header("Student Attendance")

query = st.experimental_get_query_params()
token = query.get("token", [None])[0]

if token:

    sessions_df = load_sheet_safe(
        sessions_sheet,
        ["token","subject","expiry"]
    )

    row = sessions_df[sessions_df["token"] == token]

    if not row.empty:

        subject_db = row.iloc[0]["subject"]
        expiry = datetime.strptime(row.iloc[0]["expiry"], "%Y-%m-%d %H:%M:%S")

        if datetime.now() <= expiry:

            roll = st.text_input("Roll Number")

            if roll:

                # 🔁 Always reload fresh data before checking
                reg_key = f"{roll}_{subject_db}"


				students_df = load_sheet_safe(
					students_sheet,
					["roll","name","class","gmail","mobile","subject","reg_key"]
				)


				if reg_key in students_df.get("reg_key", []).values:
					st.error("Already registered for this subject.")
					st.stop()


				students_sheet.append_row([
					roll,
					name,
					student_class,
					gmail,
					mobile,
					subject_db,
					reg_key
				])
				


                attendance_df = load_sheet_safe(
                    attendance_sheet,
                    ["roll","name","subject","timestamp","token"]
                )

                # ========== CHECK REGISTRATION ==========
                registered = students_df[
                    (students_df["roll"] == roll) &
                    (students_df["subject"] == subject_db)
                ]

                # =====================================================
                # FIRST TIME REGISTRATION
                # =====================================================
                if registered.empty:

                    st.subheader("New Registration")

                    name = st.text_input("Full Name")
                    student_class = st.selectbox("Class", ["B.Sc 1", "B.Sc 2", "B.Sc 3"])
                    gmail = st.text_input("Gmail Address")
                    mobile = st.text_input("Mobile Number")

                    if st.button("Register & Mark Attendance"):

                        # 🔒 Double-check again before writing
                        students_df = load_sheet_safe(
                            students_sheet,
                            ["roll","name","class","gmail","mobile","subject"]
                        )

                        recheck = students_df[
                            (students_df["roll"] == roll) &
                            (students_df["subject"] == subject_db)
                        ]

                        if not recheck.empty:
                            st.error("Already registered for this subject.")
                            st.stop()

                        # Save registration
                        students_sheet.append_row([
                            roll, name, student_class, gmail, mobile, subject_db
                        ])

                        # Save attendance
                        unique_key = f"{roll}_{token}"


						attendance_df = load_sheet_safe(
							attendance_sheet,
							["roll","name","subject","timestamp","token","unique_key"]
						)


						if unique_key in attendance_df.get("unique_key", []).values:
							st.warning("Attendance already marked.")
							st.stop()


						attendance_sheet.append_row([
							roll,
							name,
							subject_db,
							datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
							token,
							unique_key
						])
						
                        

                        send_email(
                            gmail,
                            "Attendance Confirmation",
                            f"Dear {name},\n\nYour attendance for {subject_db} has been marked successfully.\n\nPhysics Department"
                        )

                        st.success("Registered & Attendance Marked Successfully")
                        st.stop()

                # =====================================================
                # ALREADY REGISTERED
                # =====================================================
                else:

                    name = registered.iloc[0]["name"]
                    gmail = registered.iloc[0]["gmail"]

                    # 🔒 STRICT TOKEN CHECK
                    already_marked = attendance_df[
                        (attendance_df["roll"] == roll) &
                        (attendance_df["token"] == token)
                    ]

                    if not already_marked.empty:
                        st.warning("Attendance already marked for this session.")
                        st.stop()

                    if st.button("Mark Attendance"):

                        # 🔒 Double-check again before writing
                        attendance_df = load_sheet_safe(
                            attendance_sheet,
                            ["roll","name","subject","timestamp","token"]
                        )

                        recheck_att = attendance_df[
                            (attendance_df["roll"] == roll) &
                            (attendance_df["token"] == token)
                        ]

                        if not recheck_att.empty:
                            st.warning("Attendance already marked.")
                            st.stop()

                        unique_key = f"{roll}_{token}"


						attendance_df = load_sheet_safe(
							attendance_sheet,
							["roll","name","subject","timestamp","token","unique_key"]
						)


						if unique_key in attendance_df.get("unique_key", []).values:
							st.warning("Attendance already marked for this session.")
							st.stop()


						attendance_sheet.append_row([
							roll,
							name,
							subject_db,
							datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
							token,
							unique_key
						])

                        send_email(
                            gmail,
                            "Attendance Confirmation",
                            f"Dear {name},\n\nYour attendance for {subject_db} has been marked successfully.\n\nPhysics Department"
                        )

                        st.success("Attendance Marked Successfully")
                        st.stop()

        else:
            st.error("QR Expired.")

    else:
        st.error("Invalid QR Code.")
