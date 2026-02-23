import streamlit as st
import qrcode
import sqlite3
import pandas as pd
import uuid
from datetime import datetime, timedelta

# Database setup
conn = sqlite3.connect("attendance.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS attendance
             (roll TEXT, name TEXT, subject TEXT,
              timestamp TEXT, token TEXT)''')
conn.commit()

st.title("📚 QR Based Attendance System")

# Teacher Panel
st.sidebar.header("Teacher Panel")

subject = st.sidebar.text_input("Enter Subject Name")
duration = st.sidebar.number_input("QR Valid Duration (minutes)", min_value=1, max_value=30, value=5)

if st.sidebar.button("Generate QR"):
    token = str(uuid.uuid4())
    expiry = datetime.now() + timedelta(minutes=duration)

    st.session_state["token"] = token
    st.session_state["expiry"] = expiry
    st.session_state["subject"] = subject

    qr_data = f"?token={token}" #f"http://localhost:8501/?token={token}"
    #img = qrcode.make(qr_data)
   # st.image(img, caption="Scan to Mark Attendance")
    import io

    qr = qrcode.QRCode(
    version=1,
    box_size=10,
    border=5
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    st.image(buf, caption="Scan to Mark Attendance")

# Student Section
query_params = st.query_params
token_from_url = query_params.get("token")

if token_from_url:
    if "token" in st.session_state and token_from_url == st.session_state["token"]:
        if datetime.now() <= st.session_state["expiry"]:
            st.subheader("Mark Your Attendance")

            roll = st.text_input("Roll Number")
            name = st.text_input("Name")

            if st.button("Submit Attendance"):
                # Check duplicate
                c.execute("SELECT * FROM attendance WHERE roll=? AND token=?",
                          (roll, token_from_url))
                if c.fetchone():
                    st.warning("Attendance already marked!")
                else:
                    c.execute("INSERT INTO attendance VALUES (?,?,?,?,?)",
                              (roll, name,
                               st.session_state["subject"],
                               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                               token_from_url))
                    conn.commit()
                    st.success("Attendance Marked Successfully!")
        else:
            st.error("QR Expired!")
    else:
        st.error("Invalid QR!")

# Live Attendance Display
st.subheader("Live Attendance Record")

df = pd.read_sql_query("SELECT * FROM attendance", conn)
st.dataframe(df)

if st.button("Download CSV"):
    df.to_csv("attendance.csv", index=False)
    st.success("CSV Saved as attendance.csv")
