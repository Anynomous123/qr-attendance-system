import streamlit as st
import sqlite3
import uuid
import qrcode
import io
from datetime import datetime, timedelta

# ============================================================
# CONFIG
# ============================================================
st.set_page_config(page_title="Secure QR Attendance", layout="wide")

def now_ist():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

# ============================================================
# DATABASE
# ============================================================
conn = sqlite3.connect("attendance.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students(
    roll TEXT,
    name TEXT,
    class TEXT,
    subject TEXT,
    PRIMARY KEY (roll, subject)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sessions(
    token TEXT PRIMARY KEY,
    subject TEXT,
    expiry TEXT,
    active INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance(
    roll TEXT,
    subject TEXT,
    timestamp TEXT,
    token TEXT,
    PRIMARY KEY (roll, token)
)
""")

conn.commit()

# ============================================================
# FACULTY LOGIN
# ============================================================
if "faculty" not in st.session_state:
    st.session_state.faculty = False

st.sidebar.title("Faculty Login")

username = st.sidebar.text_input("Username")
password = st.sidebar.text_input("Password", type="password")

if st.sidebar.button("Login"):
    if username == "admin" and password == "admin123":
        st.session_state.faculty = True
        st.sidebar.success("Logged In")
    else:
        st.sidebar.error("Invalid Credentials")

# ============================================================
# TEACHER PANEL
# ============================================================
if st.session_state.faculty:

    st.header("👨‍🏫 Teacher Dashboard")

    subject = st.selectbox("Select Subject", [
        "Mechanics",
        "Optics",
        "Modern Physics"
    ])

    duration = st.slider("Token Validity (minutes)", 1, 10, 3)

    if st.button("Generate QR + Pass Key"):

        token = str(uuid.uuid4())[:6].upper()
        expiry = now_ist() + timedelta(minutes=duration)

        cursor.execute("""
        INSERT INTO sessions VALUES (?, ?, ?, 1)
        """, (token, subject,
              expiry.strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

        app_url = "https://your-app-url.streamlit.app"

        qr = qrcode.make(app_url)
        buf = io.BytesIO()
        qr.save(buf)
        buf.seek(0)

        st.image(buf)

        st.success("QR Generated")
        st.markdown(f"## 🔑 PASS KEY: `{token}`")
        st.info(f"Valid till {expiry.strftime('%H:%M:%S')}")

# ============================================================
# STUDENT SECTION
# ============================================================
st.divider()
st.header("🎓 Student Attendance Portal")

# ------------------ STEP 1: ENTER ROLL ------------------
if "roll" not in st.session_state:
    st.session_state.roll = None

if not st.session_state.roll:
    roll_input = st.text_input("Enter Roll Number")

    if st.button("Continue"):
        if roll_input:
            st.session_state.roll = roll_input.upper()
        else:
            st.warning("Enter Roll Number")

    st.stop()

roll = st.session_state.roll

# ------------------ STEP 2: CHECK REGISTRATION ------------------
cursor.execute("SELECT * FROM students WHERE roll=?", (roll,))
student = cursor.fetchone()

if not student:

    st.subheader("New Student Registration")

    name = st.text_input("Full Name")
    student_class = st.selectbox("Class", ["B.Sc 1", "B.Sc 2", "B.Sc 3"])
    subject = st.text_input("Subject (As told by teacher)")

    if st.button("Register"):
        if name and subject:
            cursor.execute("""
            INSERT INTO students VALUES (?, ?, ?, ?)
            """, (roll, name, student_class, subject))
            conn.commit()
            st.success("Registered Successfully")
            st.rerun()
        else:
            st.warning("Fill all details")

    st.stop()

# ------------------ STEP 3: ENTER PASS KEY ------------------
st.subheader("Enter Classroom Pass Key")

passkey = st.text_input("Pass Key")

if st.button("Mark Attendance"):

    cursor.execute("""
    SELECT * FROM sessions WHERE token=? AND active=1
    """, (passkey.upper(),))
    session = cursor.fetchone()

    if not session:
        st.error("Invalid Pass Key")
        st.stop()

    subject = session[1]
    expiry = datetime.strptime(session[2], "%Y-%m-%d %H:%M:%S")

    if now_ist() > expiry:
        st.error("Pass Key Expired")
        st.stop()

    # Check duplicate
    cursor.execute("""
    SELECT * FROM attendance WHERE roll=? AND token=?
    """, (roll, passkey.upper()))

    if cursor.fetchone():
        st.warning("Attendance Already Marked")
        st.stop()

    # Mark attendance
    cursor.execute("""
    INSERT INTO attendance VALUES (?, ?, ?, ?)
    """, (
        roll,
        subject,
        now_ist().strftime("%Y-%m-%d %H:%M:%S"),
        passkey.upper()
    ))
    conn.commit()

    st.success("✅ Attendance Marked Successfully")

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<hr>
<center>
Secure QR Attendance System<br>
Department of Physics
</center>
""", unsafe_allow_html=True)
