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
# SAFE DATAFRAME LOADER
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

    except Exception:
        st.warning("Email could not be sent.")


# ============================================================
# FACULTY LOGIN
# ============================================================

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


if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    st.sidebar.success(f"Logged in as: {st.session_state['faculty_name']}")
    if st.sidebar.button("Logout"):
        logout()

# ============================================================
# MAIN TITLE
# ============================================================

st.title("📚 QR Based Attendance System – Physics Department")

# ============================================================
# TEACHER DASHBOARD
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
        qr.save(buf, format="PNG")
        buf.seek(0)

        st.image(buf, caption="Scan to Mark Attendance")

    # ===================== ANALYTICS =====================

    df = load_sheet_safe(
        attendance_sheet,
        ["roll", "name", "subject", "timestamp", "token"]
    )

    sessions_df = load_sheet_safe(
        session_count_sheet,
        ["subject", "date"]
    )

    st.subheader("📋 Live Attendance Record")
    st.dataframe(df, use_container_width=True)

    if not df.empty and not sessions_df.empty:

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

        st.subheader("📊 Attendance Percentage Summary")
        st.dataframe(merged, use_container_width=True)

        st.divider()
        st.header("📈 Attendance Analytics Dashboard")

        selected_subject = st.selectbox(
            "Filter by Subject",
            ["All"] + list(total_sessions["subject"].unique())
        )

        if selected_subject != "All":
            merged_filtered = merged[merged["subject"] == selected_subject]
        else:
            merged_filtered = merged

        fig1 = px.bar(
            total_sessions,
            x="subject",
            y="Total_Classes",
            title="Total Classes per Subject"
        )
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.bar(
            merged_filtered,
            x="roll",
            y="Attendance_%",
            color="subject",
            title="Student Attendance Percentage"
        )
        st.plotly_chart(fig2, use_container_width=True)

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["date"] = df["timestamp"].dt.date

        daily_count = (
            df.groupby("date")
            .size()
            .reset_index(name="Total_Attendance")
        )

        fig3 = px.line(
            daily_count,
            x="date",
            y="Total_Attendance",
            markers=True,
            title="Daily Attendance Trend"
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.subheader("⚠️ Students Below 75% Attendance")
        low_attendance = merged_filtered[merged_filtered["Attendance_%"] < 75]

        if not low_attendance.empty:
            st.dataframe(low_attendance)
        else:
            st.success("All students above 75% attendance 🎉")

    if not df.empty:
        st.download_button(
            "Download Attendance CSV",
            df.to_csv(index=False).encode("utf-8"),
            "attendance.csv",
            "text/csv"
        )

# ============================================================
# STUDENT SECTION
# ============================================================

st.divider()
st.header("Student Attendance")

query_params = st.experimental_get_query_params()
token_from_url = query_params.get("token", [None])[0]

if token_from_url:

    sessions_df = load_sheet_safe(
        sessions_sheet,
        ["token", "subject", "expiry"]
    )

    session_row = sessions_df[sessions_df["token"] == token_from_url]

    if not session_row.empty:

        subject_db = session_row.iloc[0]["subject"]
        expiry_db = session_row.iloc[0]["expiry"]
        expiry_time = datetime.strptime(expiry_db, "%Y-%m-%d %H:%M:%S")

        if datetime.now() <= expiry_time:

            students_df = load_sheet_safe(
                students_sheet,
                ["roll", "name", "class", "gmail", "mobile"]
            )

            roll = st.text_input("Roll Number")

            if roll:

                existing_student = students_df[students_df["roll"] == roll]

                # ================= FIRST TIME =================
                if existing_student.empty:

                    st.subheader("🆕 First Time Registration")

                    name = st.text_input("Full Name")
                    student_class = st.selectbox(
                        "Class", ["B.Sc 1", "B.Sc 2", "B.Sc 3"]
                    )
                    gmail = st.text_input("Gmail Address")
                    mobile = st.text_input("Mobile Number")

                    if st.button("Register & Mark Attendance"):

                        students_sheet.append_row(
                            [roll, name, student_class, gmail, mobile]
                        )

                        attendance_sheet.append_row([
                            roll,
                            name,
                            subject_db,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            token_from_url
                        ])

                        send_email(
                            gmail,
                            "Attendance Confirmation",
                            f"Dear {name},\n\nYour attendance for {subject_db} has been marked successfully.\n\nPhysics Department"
                        )

                        st.session_state[f"marked_{token_from_url}"] = True
                        st.success("Registration & Attendance Successful!")

                # ================= EXISTING =================
                else:

                    name = existing_student.iloc[0]["name"]
                    gmail = existing_student.iloc[0]["gmail"]

                    if st.button("Mark Attendance"):

                        if f"marked_{token_from_url}" in st.session_state:
                            st.error("Attendance already submitted from this device.")
                            st.stop()

                        attendance_df = load_sheet_safe(
                            attendance_sheet,
                            ["roll", "name", "subject", "timestamp", "token"]
                        )

                        already_marked = attendance_df[
                            (attendance_df["roll"] == roll) &
                            (attendance_df["token"] == token_from_url)
                        ]

                        if not already_marked.empty:
                            st.warning("Attendance already marked!")
                        else:

                            attendance_sheet.append_row([
                                roll,
                                name,
                                subject_db,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                token_from_url
                            ])

                            send_email(
                                gmail,
                                "Attendance Confirmation",
                                f"Dear {name},\n\nYour attendance for {subject_db} has been marked successfully.\n\nPhysics Department"
                            )

                            st.session_state[f"marked_{token_from_url}"] = True
                            st.success("Attendance Marked Successfully!")

        else:
            st.error("QR Expired!")

    else:
        st.error("Invalid QR!")

else:
    st.info("Please scan a valid QR code to mark attendance.")
