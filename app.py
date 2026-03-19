import streamlit as st
import pandas as pd
import sqlite3
import datetime
import plotly.graph_objects as go
import plotly.express as px

# --- Config ---
st.set_page_config(page_title="Marathon Pace Coach", page_icon="🏃", layout="wide")

# --- DB Setup ---
conn = sqlite3.connect('marathon_data.db', check_same_thread=False)
c = conn.cursor()

def init_db():
    c.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            distance REAL,
            duration_sec INTEGER
        )
    ''')
    
    # Check if empty
    c.execute('SELECT COUNT(*) FROM records')
    if c.fetchone()[0] == 0:
        # Insert dummy data
        prev_date = datetime.date.today() - datetime.timedelta(days=15)
        dummy_data = [
            ((prev_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d"), 5.0, 1800), # 30 mins
            ((prev_date + datetime.timedelta(days=4)).strftime("%Y-%m-%d"), 10.0, 3300), # 55 mins
            ((prev_date + datetime.timedelta(days=7)).strftime("%Y-%m-%d"), 8.0, 2700), # 45 mins
            ((prev_date + datetime.timedelta(days=12)).strftime("%Y-%m-%d"), 15.0, 5000), # 1 hr 23 mins
            ((prev_date + datetime.timedelta(days=14)).strftime("%Y-%m-%d"), 5.0, 1600), # 26 mins 40 sec
        ]
        c.executemany('INSERT INTO records (date, distance, duration_sec) VALUES (?, ?, ?)', dummy_data)
        conn.commit()

init_db()

def insert_record(date, distance, duration_sec):
    c.execute('INSERT INTO records (date, distance, duration_sec) VALUES (?, ?, ?)', (date, distance, duration_sec))
    conn.commit()

def load_records():
    return pd.read_sql_query("SELECT * FROM records ORDER BY date ASC", conn)

def format_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def calculate_pace_sec(distance_km, duration_sec):
    if distance_km > 0:
        return duration_sec / distance_km
    return 0

def format_pace(pace_sec):
    minutes = int(pace_sec // 60)
    secs = int(pace_sec % 60)
    return f"{minutes}'{secs:02d}\""

# --- Sidebar (Settings) ---
st.sidebar.title("🏃 Settings")
user_name = st.sidebar.text_input("Runner Name", value="Runner")

course_options = {
    "10km": 10.0,
    "Half Marathon (21.0975km)": 21.0975,
    "Full Marathon (42.195km)": 42.195
}
selected_course = st.sidebar.selectbox("Target Course", list(course_options.keys()))
target_distance = course_options[selected_course]

st.sidebar.subheader("Target Time")
col1, col2, col3 = st.sidebar.columns(3)
with col1:
    t_hours = st.number_input("Hours", min_value=0, max_value=24, value=4)
with col2:
    t_minutes = st.number_input("Mins", min_value=0, max_value=59, value=0)
with col3:
    t_seconds = st.number_input("Secs", min_value=0, max_value=59, value=0)

calc_btn = st.sidebar.button("Calculate Target")

weekly_target_distance = st.sidebar.number_input("Weekly Goal (km)", min_value=1.0, max_value=200.0, value=40.0, step=5.0)

# --- Main Content ---
st.title(f"{user_name}'s Marathon Pace Coach 🥇")
st.markdown("---")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("🎯 Target Pace Calculation")
    target_sec = (t_hours * 3600) + (t_minutes * 60) + t_seconds
    target_pace_sec = target_sec / target_distance if target_distance > 0 else 0
    target_pace_str = format_pace(target_pace_sec)
    
    st.info(f"**Target Pace:** {target_pace_str} / km")
    
    # Passing times
    st.subheader("Expected Passing Times")
    passing_distances = [5, 10, 20, 30, 40]
    
    passing_data = []
    for d in passing_distances:
        if d <= target_distance:
            t = target_pace_sec * d
            passing_data.append({"Distance (km)": f"{d}km", "Passing Time": format_time(t)})
    
    if target_distance not in passing_distances:
        passing_data.append({"Distance (km)": f"Finish ({target_distance}km)", "Passing Time": format_time(target_sec)})
        
    df_passing = pd.DataFrame(passing_data)
    st.table(df_passing)

with col2:
    st.header("📝 Training Record Input")
    with st.form("record_form"):
        r_date = st.date_input("Date", datetime.date.today())
        r_distance = st.number_input("Distance (km)", min_value=0.1, step=0.1)
        st.write("Running Time")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            r_hours = st.number_input("Hr", min_value=0, max_value=24, value=0)
        with rc2:
            r_minutes = st.number_input("Min", min_value=0, max_value=59, value=30)
        with rc3:
            r_seconds = st.number_input("Sec", min_value=0, max_value=59, value=0)
            
        submitted = st.form_submit_button("Save Record")
        if submitted:
            total_r_sec = (r_hours * 3600) + (r_minutes * 60) + r_seconds
            if r_distance > 0 and total_r_sec > 0:
                insert_record(r_date.strftime("%Y-%m-%d"), r_distance, total_r_sec)
                st.success("Record saved successfully!")
                st.rerun()
            else:
                st.error("Please enter valid distance and time.")

st.markdown("---")
st.header("📊 Training Performance Visualization")

df_records = load_records()

if not df_records.empty:
    df_records['date'] = pd.to_datetime(df_records['date'])
    
    # Calculate Weekly Distance (past 7 days including today)
    today = pd.to_datetime(datetime.date.today())
    last_week = today - pd.Timedelta(days=14) # expanded to 14 for dummy data visibility
    recent_records = df_records[(df_records['date'] >= last_week) & (df_records['date'] <= today)]
    accumulated_distance = recent_records['distance'].sum()
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Goal Achievement Rate (Recent 14 Days)")
        # Gauge Chart
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = accumulated_distance,
            title = {'text': f"Recent Distance (Goal: {weekly_target_distance}km)"},
            delta = {'reference': weekly_target_distance},
            gauge = {
                'axis': {'range': [None, max(weekly_target_distance, accumulated_distance) * 1.2]},
                'bar': {'color': "#1f77b4" if accumulated_distance < weekly_target_distance else "#2ca02c"},
                'steps' : [
                    {'range': [0, weekly_target_distance * 0.5], 'color': "rgba(255, 0, 0, 0.2)"},
                    {'range': [weekly_target_distance * 0.5, weekly_target_distance], 'color': "rgba(255, 255, 0, 0.2)"},
                ],
                'threshold' : {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': weekly_target_distance
                }
            }
        ))
        fig_gauge.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_chart2:
        st.subheader("Pace Change Trend")
        # Line chart for pace trend
        df_records['pace_sec'] = df_records['duration_sec'] / df_records['distance']
        # Convert pace_sec to minutes for better Y-axis read (e.g., 5.5 means 5m30s)
        df_records['pace_min'] = df_records['pace_sec'] / 60.0
        
        # Sort by date
        df_sorted = df_records.sort_values(by='date')
        
        # Plot Y axis reversed because lower pace is faster/better
        fig_line = px.line(df_sorted, x='date', y='pace_min', markers=True, 
                           labels={"date": "Date", "pace_min": "Pace (min/km)"},
                           title="Average Pace / Session")
        
        # Format axes
        fig_line.update_yaxes(autorange="reversed")
        
        st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("No training records found. Add some records to see charts!")
