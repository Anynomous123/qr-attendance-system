import streamlit as st
import qrcode
import pandas as pd
import uuid
import io
from datetime import datetime, timedelta

import gspread
from google.oauth2.service_account import Credentials

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

# ============================================================
# FACULTY LOGIN SYSTEM
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
    st.sidebar.success("Logged out")


if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    st.sidebar.write(f"Logged in as: {st.session_state['faculty_name']}")
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

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        st.image(buf, caption="Scan to Mark Attendance")

    # ----------------- Live Attendance -----------------

    st.subheader("Live Attendance Record")

    df = pd.DataFrame(attendance_sheet.get_all_records())
    st.dataframe(df)

    # ----------------- Attendance Percentage -----------------

    st.subheader("Attendance Percentage Summary")

    if not df.empty:

        sessions_df = pd.DataFrame(session_count_sheet.get_all_records())

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

    # ----------------- Download -----------------

    st.subheader("Download Attendance")

    if not df.empty:
        csv_data = df.to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download Attendance CSV",
            data=csv_data,
            file_name="attendance.csv",
            mime="text/csv",
        )

# ============================================================
# STUDENT SECTION
# ============================================================

st.divider()
st.header("Student Attendance")

query_params = st.query_params
token_from_url = query_params.get("token")

if token_from_url:

    sessions_data = sessions_sheet.get_all_records()
    sessions_df = pd.DataFrame(sessions_data)

    if not sessions_df.empty:

        session_row = sessions_df[sessions_df["token"] == token_from_url]

        if not session_row.empty:

            subject_db = session_row.iloc[0]["subject"]
            expiry_db = session_row.iloc[0]["expiry"]
            expiry_time = datetime.strptime(expiry_db, "%Y-%m-%d %H:%M:%S")

            if datetime.now() <= expiry_time:

                st.subheader(f"Subject: {subject_db}")

                roll = st.text_input("Roll Number")
                name = st.text_input("Name")

                if st.button("Submit Attendance"):

                    attendance_data = attendance_sheet.get_all_records()
                    attendance_df = pd.DataFrame(attendance_data)

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
                        st.success("Attendance Marked Successfully!")

            else:
                st.error("QR Expired!")

        else:
            st.error("Invalid QR!")
    else:
        st.error("No active sessions found.")

else:
    st.info("Please scan a valid QR code to mark attendance.")
