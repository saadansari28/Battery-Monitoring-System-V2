import serial
import time
import csv
import os
from flask import Flask, render_template, jsonify, Response, render_template_string
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg') # Use a non-interactive backend for server-side plotting
import matplotlib.pyplot as plt
import io
from fpdf import FPDF

# --- Configuration ---
SERIAL_PORT = 'COM3'  # <-- IMPORTANT: CHANGE THIS to your Arduino's port!
BAUD_RATE = 9600
CSV_FILE = 'readings.csv'
NEW_BATTERY_VOLTAGE = 4.2 # Ideal max voltage of a healthy Li-ion battery for SOH calculation

app = Flask(__name__)
# Tells Flask to look for index2.html in the 'templates' folder
app.template_folder = 'templates'

# --- Initialize Serial Connection ---
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
    time.sleep(2)
    print(f"Successfully connected to Arduino on {SERIAL_PORT}")
except serial.SerialException as e:
    print(f"Error: Could not open serial port '{SERIAL_PORT}'.")
    print("Dashboard will run but show a disconnected state.")
    ser = None

# --- Data Logging ---
def log_data(data_dict):
    """Appends a new reading from a dictionary to the CSV file."""
    file_exists = os.path.isfile(CSV_FILE)
    try:
        with open(CSV_FILE, mode='a', newline='') as file:
            # The keys of the dictionary will be the headers
            writer = csv.DictWriter(file, fieldnames=data_dict.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_dict)
    except IOError as e:
        print(f"Error writing to CSV file: {e}")

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main dashboard page."""
    return render_template('index2.html')

@app.route('/data')
def get_data():
    """Reads data from Arduino and sends it to the webpage."""
    if not ser:
        return jsonify({"error": f"Arduino not connected on port {SERIAL_PORT}."})

    try:
        line = ser.readline().decode('utf-8').strip()
        if line and ',' in line:
            parts = line.split(',')
            if len(parts) == 3:
                voltage, current, soc = map(float, parts)
                
                # --- Prepare data for the new dashboard ---
                power = voltage * current  # Calculate Power in mW
                
                # Create a dictionary of all data
                data_packet = {
                    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "voltage": voltage,
                    "current": current,
                    "soc": soc,
                    "power": power,
                    "temperature": 25.5,  # Placeholder value
                    "soh": min((voltage / NEW_BATTERY_VOLTAGE) * 100, 100), # Simple SOH calculation
                    "cycles": 1,          # Placeholder value
                    "connected": True
                }
                
                log_data(data_packet) # Log the complete packet
                
                return jsonify(data_packet)
    except Exception as e:
        print(f"Could not read or parse data from Arduino: {e}")
        return jsonify({"error": "Error reading data from Arduino."})

    return jsonify({})

@app.route('/download_report')
def download_report():
    """Generates a detailed PDF report from the logged data."""
    if not os.path.exists(CSV_FILE):
        return render_template_string("<html><body><h1>Error</h1><p>No data file found. Let the system run for a while.</p><a href='/'>Go Back</a></body></html>"), 404

    df = pd.read_csv(CSV_FILE)
    if df.empty:
        return render_template_string("<html><body><h1>Error</h1><p>Data file is empty. No report to generate.</p><a href='/'>Go Back</a></body></html>"), 404

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # --- 1. Perform Calculations for Summary ---
    summary = {
        "avg_voltage": df['voltage'].mean(),
        "avg_current": df['current'].mean(),
        "avg_power": df['power'].mean(),
        "max_voltage": df['voltage'].max(),
        "latest_soc": df['soc'].iloc[-1],
        "estimated_soh": df['soh'].iloc[-1],
    }

    # --- 2. Create the Chart ---
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()
    ax1.plot(df['timestamp'], df['voltage'], color='#6a11cb', label='Voltage (V)')
    ax2.plot(df['timestamp'], df['current'], color='#2575fc', label='Current (mA)')
    ax1.set_xlabel('Time'); ax1.set_ylabel('Voltage (V)', color='#6a11cb'); ax2.set_ylabel('Current (mA)', color='#2575fc')
    plt.title('Battery Voltage & Current Report'); fig.legend(loc="upper right", bbox_to_anchor=(1,1), bbox_transform=ax1.transAxes)
    fig.tight_layout(); img_buffer = io.BytesIO(); plt.savefig(img_buffer, format='PNG'); img_buffer.seek(0); plt.close(fig)

    # --- 3. Assemble the PDF ---
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20); pdf.cell(0, 10, 'Battery Performance Report', 0, 1, 'C')
    pdf.set_font('Arial', '', 11); pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'C'); pdf.ln(5)

    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, 'Performance Summary', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 8,
        f"  - Latest State of Charge (SoC): {summary['latest_soc']:.2f}%\n"
        f"  - Estimated State of Health (SoH): {summary['estimated_soh']:.2f}%\n"
        f"  - Average Voltage: {summary['avg_voltage']:.2f} V\n"
        f"  - Average Current: {summary['avg_current']:.2f} mA\n"
        f"  - Average Power: {summary['avg_power']:.2f} mW"
    )
    pdf.ln(5)

    # --- NEW: Health Analysis Section ---
    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, 'Health Analysis', 0, 1)
    soh = summary['estimated_soh']
    if soh > 90:
        health_status = "Excellent"
        health_desc = "Battery is performing at or near its original capacity."
        pdf.set_text_color(34, 139, 34) # Forest Green
    elif 80 < soh <= 90:
        health_status = "Good"
        health_desc = "Battery shows minor capacity loss, which is normal for its age."
        pdf.set_text_color(50, 205, 50) # Lime Green
    elif 60 < soh <= 80:
        health_status = "Average"
        health_desc = "Battery has noticeable degradation. Performance may be reduced."
        pdf.set_text_color(255, 165, 0) # Orange
    else:
        health_status = "Poor"
        health_desc = "Significant capacity loss. Consider replacement for optimal performance."
        pdf.set_text_color(220, 20, 60) # Crimson Red

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(40, 8, "Overall Health:", 0, 0)
    pdf.cell(0, 8, health_status, 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.set_text_color(0, 0, 0) # Reset to black
    pdf.multi_cell(0, 8, f"  - Note: {health_desc}")
    pdf.ln(10)


    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, 'Readings Chart', 0, 1)
    pdf.image(img_buffer, x=10, w=190); pdf.ln(100)

    pdf.set_font('Arial', 'B', 14); pdf.cell(0, 10, 'Detailed Log', 0, 1)
    pdf.set_font('Arial', 'B', 10)
    col_width = pdf.w / 5.5
    headers = ['Timestamp', 'Voltage (V)', 'Current (mA)', 'Power (mW)', 'SoC (%)']
    for header in headers:
        pdf.cell(col_width, 10, header, 1, 0, 'C')
    pdf.ln()
    pdf.set_font('Arial', '', 9)
    for i, row in df.iterrows():
        pdf.cell(col_width, 8, str(row['timestamp'].strftime('%d-%b %H:%M')), 1, 0)
        pdf.cell(col_width, 8, f"{row['voltage']:.2f}", 1, 0)
        pdf.cell(col_width, 8, f"{row['current']:.2f}", 1, 0)
        pdf.cell(col_width, 8, f"{row['power']:.2f}", 1, 0)
        pdf.cell(col_width, 8, f"{row['soc']:.2f}", 1, 1)

    # --- 4. Send PDF to Browser ---
    return Response(
        pdf.output(dest='S').encode('latin-1'),
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=battery_report.pdf'}
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
