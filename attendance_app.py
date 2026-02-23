import streamlit as st
##########################################################################
import streamlit as st

# -------------------------
# Faculty Login System
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
##############################################################################
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    st.sidebar.write(f"Logged in as: {st.session_state['faculty_name']}")
    if st.sidebar.button("Logout"):
        logout()
############################################################################
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

c.execute('''CREATE TABLE IF NOT EXISTS sessions
             (token TEXT, subject TEXT, expiry TEXT)''')
conn.commit()

# Teacher Panel
st.sidebar.header("Teacher Panel")

subject = st.sidebar.text_input("Enter Subject Name")
duration = st.sidebar.number_input("QR Valid Duration (minutes)", min_value=1, max_value=30, value=5)

#if st.sidebar.button("Generate QR"):
    #token = str(uuid.uuid4())
    #expiry = datetime.now() + timedelta(minutes=duration)

    #st.session_state["token"] = token
    #st.session_state["expiry"] = expiry
    #st.session_state["subject"] = subject
    #app_url = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"
    #qr_data = f"{app_url}/?token={token}" 
    #import io

    #qr = qrcode.QRCode(
    #version=1,
    #box_size=10,
    #border=5
    #)
    #qr.add_data(qr_data)
    #qr.make(fit=True)

    #img = qr.make_image(fill_color="black", back_color="white")

    #buf = io.BytesIO()
    #img.save(buf, format="PNG")
    #buf.seek(0)

    #st.image(buf, caption="Scan to Mark Attendance")


if st.session_state["logged_in"]:

    st.header("Faculty Dashboard")

    # QR generation code here
    # Attendance table
    # Download CSV    
	if st.sidebar.button("Generate QR"):
		token = str(uuid.uuid4())
		expiry = datetime.now() + timedelta(minutes=duration)

		c.execute("INSERT INTO sessions VALUES (?,?,?)",
		          (token, subject,
		           expiry.strftime("%Y-%m-%d %H:%M:%S")))
		conn.commit()

		app_url = "https://qr-attendance-system-ngubz54ivcsykf753qfbdk.streamlit.app"  # your actual URL
		qr_data = f"{app_url}/?token={token}"
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
    

    #img = qrcode.make(qr_data)
    #st.image(img, caption="Scan to Mark Attendance")

# Student Section
#query_params = st.query_params
#token_from_url = query_params.get("token")

#if token_from_url:
    #if "token" in st.session_state and token_from_url == st.session_state["token"]:
       # if datetime.now() <= st.session_state["expiry"]:
            #st.subheader("Mark Your Attendance")

            #roll = st.text_input("Roll Number")
            #name = st.text_input("Name")

            #if st.button("Submit Attendance"):
            #    # Check duplicate
           #     c.execute("SELECT * FROM attendance WHERE roll=? AND token=?",
          #                (roll, token_from_url))
         #       if c.fetchone():
        #            st.warning("Attendance already marked!")
       #         else:
      #              c.execute("INSERT INTO attendance VALUES (?,?,?,?,?)",
     #                         (roll, name,
    #                           st.session_state["subject"],
          #                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #                       token_from_url))
         #           conn.commit()
       #             st.success("Attendance Marked Successfully!")
      #  else:
     #       st.error("QR Expired!")
    #else:
       # st.error("Invalid QR!")
        
        
	query_params = st.experimental_get_query_params()
	token_from_url = query_params.get("token", [None])[0]

	if token_from_url:
		c.execute("SELECT subject, expiry FROM sessions WHERE token=?",
		          (token_from_url,))
		session = c.fetchone()

		if session:
		    subject_db, expiry_db = session
		    expiry_time = datetime.strptime(expiry_db, "%Y-%m-%d %H:%M:%S")

		    if datetime.now() <= expiry_time:

		        st.subheader("Mark Your Attendance")

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

# Live Attendance Display
#st.subheader("Live Attendance Record")

#df = pd.read_sql_query("SELECT * FROM attendance", conn)

#st.dataframe(df)

#if st.button("Download CSV"):
    #csv = df.to_csv(index=False).encode('utf-8')
    
    #st.download_button(
   #	label="Download Attendance CSV",
  #	data=csv,
  #	file_name="attendance.csv",
  #	mime="text/csv"
  #  )
 #   #df.to_csv("attendance.csv", index=False)
#    st.success("CSV Saved as attendance.csv")
    

# Live Attendance Display
	st.subheader("Live Attendance Record")

	df = pd.read_sql_query("SELECT * FROM attendance", conn)
	st.dataframe(df)

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

