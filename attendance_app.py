import streamlit as st
import qrcode
import pandas as pd
import uuid
import io
from datetime import datetime, timedelta, date
today = date.today()
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
import sqlite3

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(page_title="QR Attendance System", layout="wide")

st.markdown("""
<style>


/* Background */
.main {
    background-color: rgba(224, 242, 255, 0.85);
}


/* Sidebar background */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(0, 123, 255, 0.7), rgba(0, 86, 179, 0.7));
}


/* Sidebar labels only */
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stMarkdown {
    color: white !important;
    font-weight: 600;
}


/* Fix selectbox text color */
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
    color: black !important;
}


/* Buttons */
div.stButton > button {
    background: linear-gradient(90deg, rgba(0, 123, 255, 0.7), rgba(0, 86, 179, 0.7));
    color: white;
    border-radius: 10px;
    border: none;
    font-weight: 600;
    padding: 8px 16px;
}


div.stButton > button:hover {
    background: linear-gradient(90deg, rgba(0, 86, 179, 1), rgba(0, 64, 133, 1));
    color: white;
}


/* Metric Card with glass effect */
.metric-card {
    background: rgba(224, 242, 255, 0.7);
    backdrop-filter: blur(8px);
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 4px 15px rgba(0,0,0,0.08);
    text-align: center;
}


</style>
""", unsafe_allow_html=True)
# ============================================================
# IST TIME FUNCTION
# ============================================================

def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ============================================================
# DATABASE CONNECTION (HIGH CONCURRENCY SAFE)
# ============================================================

conn = sqlite3.connect(
    "attendance.db",
    check_same_thread=False,
    timeout=30,
    isolation_level=None
)

cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")

# ============================================================
# CREATE TABLES
# ============================================================

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    link TEXT,
    timestamp TEXT
)
""")


conn.commit()

# ============================================================
# 📢 FLASH CLASS NOTICES
# ============================================================
st.markdown("## 📢 Class Notices")

notices_df = pd.read_sql_query(
    "SELECT * FROM notices ORDER BY id DESC LIMIT 5",
    conn
)

if not notices_df.empty:
    for _, row in notices_df.iterrows():
        st.markdown(f"""
        <div style="
            background: linear-gradient(90deg, rgba(0,123,255,0.1), rgba(0,86,179,0.1));
            animation: pulse 2s infinite;
            padding: 12px;
            border-left: 5px solid #007bff;
            border-radius: 8px;
            margin-bottom: 10px;">
            <b>{row['title']}</b><br>
            {row['content']}<br>
            {"🔗 <a href='"+row['link']+"' target='_blank'>Open Resource</a>" if row['link'] else ""}
            <br><small>Posted on: {row['timestamp']}</small>
        </div>
        """, unsafe_allow_html=True)
else:
    st.info("No notices available.")
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
# LOGIN SYSTEM
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

def login():
    st.sidebar.subheader("Faculty Login")
    user = st.sidebar.text_input("Username")
    pwd = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        users = st.secrets["FACULTY_USERS"]
        if user in users and users[user] == pwd:
            st.session_state.logged_in = True
            st.session_state.faculty_name = user
            st.sidebar.success("Login Successful")
        else:
            st.sidebar.error("Invalid Credentials")

if not st.session_state.logged_in:
    login()
else:
    st.sidebar.success(f"Logged in as {st.session_state.faculty_name}")
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False

# ============================================================
# UNIVERSITY BRANDED HEADER - GREEN THEME
# ============================================================


st.markdown("""
<style>
.header-container {
    background: linear-gradient(90deg, rgba(0, 123, 255, 0.7), rgba(0, 86, 179, 0.7));
    padding: 20px;
    border-radius: 10px;
    color: white;
}
</style>
""", unsafe_allow_html=True)


header_col1, header_col2 = st.columns([1, 6])


with header_col1:
    st.image("logo.png", width=95)


with header_col2:
    st.markdown("""
    <div class="header-container">
        <h1 style='margin-bottom:5px;'>
        G. B. Pant Memorial Govt. College Rampur Bushahr 
        </h1>
        <h4 style='margin-top:0px;'>
        Shimla 172001
        </h4>
        <p style='font-size:18px; margin-top:10px;'>
        Department of Physics – QR Smart Attendance System
        </p>
    </div>
    """, unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import pagesizes
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image
import io
from datetime import datetime




def generate_pdf(attendance_df, selected_class, subject, total_sessions, attendance_percent):


    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=pagesizes.A4)
    elements = []


    styles = getSampleStyleSheet()


    # University Header
    elements.append(Paragraph(
        "<b>G. B. Pant Memorial Govt. College</b>", styles['Title']))
    elements.append(Paragraph(
        "Rampur Bushahr, Shimla", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))


    # Report Title
    elements.append(Paragraph(
        f"<b>Attendance Report</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.2 * inch))


    # Report Details
    elements.append(Paragraph(
        f"Class: {selected_class}", styles['Normal']))
    elements.append(Paragraph(
        f"Subject: {subject}", styles['Normal']))
    elements.append(Paragraph(
        f"Total Sessions: {total_sessions}", styles['Normal']))
    elements.append(Paragraph(
        f"Attendance Percentage: {attendance_percent}%", styles['Normal']))
    elements.append(Paragraph(
        f"Generated On: {datetime.now().strftime('%d-%m-%Y %H:%M')}", styles['Normal']))


    elements.append(Spacer(1, 0.3 * inch))


    # Table Data
    data = [attendance_df.columns.tolist()] + attendance_df.values.tolist()


    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))


    elements.append(table)


    doc.build(elements)
    buffer.seek(0)


    return buffer
# ============================================================
# TEACHER PANEL
# ============================================================
st.sidebar.markdown("## 🎓 Faculty Dashboard")
st.sidebar.markdown("---")
if st.session_state.logged_in:

    st.sidebar.header("Teacher Panel")

    selected_class = st.sidebar.selectbox(
        "Select Class",
        ["B.Sc 1", "B.Sc 2", "B.Sc 3"]
    )
    # ================= SUBJECT MAPPING BY CLASS =================
    class_subjects = {
        "B.Sc 1": [
            "Mechanics (PHYS101TH)",
            "Electricity, Magnetism & EMT (PHYS102TH)",
            "Mechanics (PHYS101PR)",
            "Electricity, Magnetism & EMT (PHYS102PR)"    
         ],
         "B.Sc 2": [
             "Statistical & Thermal Physics (PHYS201TH)",
             "Waves and Optics (PHYS202TH)",
             "Computational Physics (PHYS204TH)",
             "Electronic Circuits & Metwork Skills (PHYS205TH)",
             "Statistical & Thermal Physics (PHYS201PR)",
             "Waves and Optics (PHYS202PR)", 
             "Computational Physics (PHYS204SE)", 
             "Electronic Circuits & Metwork Skills (PHYS205SE)"
         ],
         "B.Sc 3": [
             "Modern Physics (PHYS301TH)",
             "Nuclear and Particle Physics (PHYS304TH)",
             "Radiation Safety (PHYS307TH)",
             "Renewable Energy and Energy Harvesting (PHYS310TH)",
             "Modern Physics (PHYS301PR)", 
             "Nuclear and Particle Physics (PHYS304TU)",  
             "Radiation Safety (PHYS307SE)",
             "Renewable Energy and Energy Harvesting (PHYS310TH)"
         ]
    }
    
    
    subjects = class_subjects[selected_class]
    subject = st.sidebar.selectbox("Select Subject", subjects)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"""
    ### 📘 Current Selection
    - **Class:** {selected_class}
    - **Subject:** {subject}
    """)

    duration = st.sidebar.number_input("QR Valid Duration (minutes)", 1, 60, 5)

    # ================= GENERATE QR =================
    validity_seconds = st.slider(
        "Select QR Validity (seconds)",
        min_value=10,
        max_value=300, # 5 minutes
        value=60,
        step=10
    )
    
    if st.sidebar.button("Generate QR"):

        token = str(uuid.uuid4())
        expiry = now_ist() + timedelta(seconds=validity_seconds)

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
        st.success(f"✅ QR Generated (Valid for {validity_seconds} seconds)")
        
    st.divider()
    st.subheader("👩‍🏫 Teacher Panel – Publish Notice")

    with st.expander("➕ Create New Notice", expanded=True):

        notice_title = st.text_input("Notice Title")
        notice_content = st.text_area("Notice Description")
        notice_link = st.text_input("Optional Link (YouTube / PDF / PPT / Drive)")

        if st.button("📢 Publish Notice"):

            if notice_title and notice_content:
                cursor.execute(
                "INSERT INTO notices (title, content, link, timestamp) VALUES (?, ?, ?, ?)",
                (
                    notice_title,
                    notice_content,
                    notice_link,
                    now_ist().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            conn.commit()

            st.success("✅ Notice Published Successfully")
            st.rerun()
        else:
            st.warning("Please fill Title and Description")
        
        
    # ============================================================
    # DELETE OLD NOTICES
    # ============================================================

    st.divider()
    st.subheader("🗑 Manage / Delete Notices")

    notices_df = pd.read_sql_query(
        "SELECT * FROM notices ORDER BY id DESC",
        conn
    )

    if not notices_df.empty:

        for _, row in notices_df.iterrows():

            col1, col2 = st.columns([6, 1])

            with col1:
                st.markdown(f"""
                <div style="
                    font-size: 12px;
                    line-height: 1.2;
                    padding: 4px 0;
                ">
                    <b>{row['title']}</b><br>
                    {row['content']}<br>
                    <span style="color:gray;">🕒 {row['timestamp']}</span>
                </div>
            """, unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="small-delete">', unsafe_allow_html=True)
                delete_clicked = st.button("❌", key=f"delete_{row['id']}")
                st.markdown('</div>', unsafe_allow_html=True)

                if delete_clicked:
                    cursor.execute(
                        "DELETE FROM notices WHERE id = ?",
                        (row['id'],)
                    )
                    conn.commit()
                    st.rerun()

            st.markdown("---")

    else:
        st.info("No notices available to delete.")


    # ================= ANALYTICS =================

    attendance_df = pd.read_sql_query(
        "SELECT * FROM attendance WHERE subject=?",
        conn,
        params=(subject,)
    )


    total_present = len(attendance_df)

    #st.subheader("📋 Live Attendance Record")
    #st.dataframe(attendance_df, use_container_width=True)
    st.markdown("## 📊 Attendance Dashboard")


    col1, col2, col3 = st.columns(3)


    #total_present = len(attendance_df)

    sessions_df = pd.read_sql_query("""
        SELECT DISTINCT subject, DATE(expiry) as session_date
        FROM sessions
    """, conn)

    total_sessions = len(sessions_df)

    #st.metric("Total Sessions", total_sessions)
    
    #total_sessions = pd.read_sql_query(
    #    "SELECT COUNT(*) as total FROM sessions WHERE subject=?",
    #    conn,
    #    params=(subject,)
    #)["total"][0]


    attendance_percent = 0
    if total_sessions > 0 and total_present > 0:
        attendance_percent = round((total_present / total_sessions), 2)


    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Total Present</h3>
            <h1 style="color:#198754;">{total_present}</h1>
        </div>
        """, unsafe_allow_html=True)


    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Total Sessions</h3>
            <h1 style="color:#0d6efd;">{total_sessions}</h1>
        </div>
        """, unsafe_allow_html=True)


    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>Avg_Attendance/Session</h3>
            <h1 style="color:#dc3545;">{attendance_percent}</h1>
        </div>
        """, unsafe_allow_html=True)


    st.markdown("<br>", unsafe_allow_html=True)


    st.dataframe(attendance_df, use_container_width=True)


    if not attendance_df.empty:
        st.markdown("### 📥 Download PDF Report")


        pdf_file = generate_pdf(
            attendance_df,
            selected_class,
            subject,
            total_sessions,
            attendance_percent
        )


        st.download_button(
            label="📄 Download Attendance Report (PDF)",
            data=pdf_file,
            file_name=f"{selected_class}_{subject}_Attendance_Report.pdf",
            mime="application/pdf"
        )

        total_sessions = pd.read_sql_query(
            "SELECT subject, COUNT(*) as Total_Classes FROM sessions GROUP BY subject",
            conn
        )

        attendance_count = attendance_df.groupby(
            ["roll", "subject"]
        ).size().reset_index(name="Classes_Attended")

        merged = attendance_count.merge(total_sessions, on="subject")
        merged["Attendance_%"] = (
            merged["Classes_Attended"] /
            merged["Total_Classes"] * 100
        ).round(2)

        st.subheader("📊 Attendance % Summary")
        st.dataframe(merged, use_container_width=True)

        #fig = px.bar(merged, x="roll", y="Attendance_%")
        fig = px.bar(
            merged,
            x="roll",
            y="Attendance_%",
            color="Attendance_%",
            color_continuous_scale="Greens"
        )


        fig.update_layout(
           plot_bgcolor="white",
           paper_bgcolor="white",
           title="Attendance Percentage by Student",
           title_x=0.3
        )
        st.plotly_chart(fig, use_container_width=True)

        # EXPORT CURRENT SUBJECT
        csv_subject = attendance_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download Current Subject CSV",
            csv_subject,
            f"{subject}_attendance.csv",
            "text/csv"
        )

        # EXPORT ALL SUBJECTS
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
#st.header("Student Attendance")
st.markdown("""
## 🎓 Student Attendance Portal
<div style='background:linear-gradient(90deg,rgba(0, 123, 255, 0.7),rgba(0, 86, 179, 0.7));
padding:15px;
border-radius:10px;
color:white;
font-size:18px;'>
Scan the QR Code and Enter Your Roll Number
</div>
""", unsafe_allow_html=True)

query = st.experimental_get_query_params()
token = query.get("token", [None])[0]


if token:


    cursor.execute("SELECT * FROM sessions WHERE token=?", (token,))
    session = cursor.fetchone()


    if session:


        subject_db = session[1]
        expiry = datetime.strptime(session[2], "%Y-%m-%d %H:%M:%S")


        if now_ist() > expiry:
            st.error("QR Expired")
            st.stop()
            
        # ================= LIVE COUNTER =================


        cursor.execute(
            "SELECT COUNT(*) FROM attendance WHERE token=?",
            (token,)
        )
        count = cursor.fetchone()[0]


        st.info(f"👥 Students Marked: {count}")


        if count >= 100:
            st.error("Attendance Closed: 100 Students Reached")
            st.stop()


        # ================= ROLL INPUT =================


        roll = st.text_input("Roll Number")


        if roll:


            cursor.execute(
                "SELECT * FROM students WHERE roll=? AND subject=?",
                (roll, subject_db)
            )
            registered = cursor.fetchone()


            # ================= FIRST TIME REGISTRATION =================
            if not registered:


                st.subheader("New Registration")


                name = st.text_input("Full Name")
                student_class = st.selectbox(
                    "Class",
                    ["B.Sc 1", "B.Sc 2", "B.Sc 3"]
                )
                gmail = st.text_input("Gmail Address")
                mobile = st.text_input("Mobile Number")


                if st.button("Register & Mark Attendance"):


                    # 🔥 CHECK DAILY DUPLICATE
                    today_date = now_ist().strftime("%Y-%m-%d")


                    cursor.execute("""
                        SELECT 1 FROM attendance
                        WHERE roll=?
                        AND subject=?
                        AND DATE(timestamp)=?
                    """, (roll, subject_db, today_date))


                    if cursor.fetchone():
                        st.warning("⚠ Attendance already marked today for this subject!")
                        st.stop()


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


                        send_email(
                            gmail,
                            "Attendance Confirmed",
                            f"Dear {name}, your attendance is marked."
                        )


                        st.success("✅ Registered & Attendance Marked")
                        st.session_state.roll = roll # 👈 ADD THIS


                    except sqlite3.IntegrityError:
                        st.warning("Already registered or attendance marked.")


            # ================= ALREADY REGISTERED =================
            else:


                name = registered[1]
                gmail = registered[3]


                if st.button("Mark Attendance"):


                    # 🔥 CHECK DAILY DUPLICATE (MAIN FIX)
                    today_date = now_ist().strftime("%Y-%m-%d")


                    cursor.execute("""
                        SELECT 1 FROM attendance
                        WHERE roll=?
                        AND subject=?
                        AND DATE(timestamp)=?
                    """, (roll, subject_db, today_date))


                    if cursor.fetchone():
                        st.warning("⚠ Attendance already marked today for this subject!")
                        st.stop()


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


                        send_email(
                            gmail,
                            "Attendance Confirmed",
                            f"Dear {name}, your attendance is marked."
                        )


                        st.success("✅ Attendance Marked Successfully")


                    except sqlite3.IntegrityError:
                        st.warning("Attendance already marked.")


        else:
            st.error("Invalid QR Code.")
        
st.markdown("""
<hr style='border:1px solid rgba(0, 123, 255, 0.7);'>
<center style='color:rgba(0, 123, 255, 0.7); font-weight:bold;'>
© 2026 G. B. Pant Memorial Govt. College, Rampur Bushahr, Shimla
Department of Physics | Smart Attendance Monitoring System
</center>
""", unsafe_allow_html=True)
