import serial
import serial.tools.list_ports
import time
import csv
import os
from flask import Flask, jsonify, Response, render_template, render_template_string
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
from fpdf import FPDF

# --- Configuration ---
SERIAL_PORT = 'COM3'  # Change if needed
BAUD_RATE = 9600
CSV_FILE = 'readings.csv'
NEW_BATTERY_VOLTAGE = 4.2

app = Flask(__name__)

# --- Global Variables ---
ser = None
last_data = {
    "voltage": 0,
    "current": 0,
    "soc": 0,
    "power": 0,
    "temperature": 0,
    "soh": 0,
    "cycles": 0,
    "connected": False,
    "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "error": "Initializing..."
}

# --- Find Available Ports ---
def list_serial_ports():
    """List all available COM ports"""
    ports = serial.tools.list_ports.comports()
    available = []
    for port in ports:
        available.append(f"{port.device} - {port.description}")
    return available

# --- Initialize Serial Connection ---
def init_serial():
    """Initialize serial connection with retry logic"""
    global ser
    
    print("\n=== Checking Available Serial Ports ===")
    ports = list_serial_ports()
    if not ports:
        print("❌ No serial ports found!")
        return False
    
    for port in ports:
        print(f"📍 {port}")
    
    try:
        if ser and ser.is_open:
            print(f"Closing existing connection on {ser.port}")
            ser.close()
            time.sleep(0.5)
        
        print(f"\n🔌 Attempting to connect to {SERIAL_PORT}...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)  # Wait for Arduino to reset
        
        # Clear buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Test read
        print("📡 Testing connection...")
        for i in range(3):
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            print(f"   Test read {i+1}: '{line}'")
            if line and ',' in line:
                print(f"✅ Successfully connected to Arduino on {SERIAL_PORT}")
                return True
        
        print("⚠️  Connected but no valid data received")
        return True
        
    except serial.SerialException as e:
        print(f"❌ Error: Could not open serial port '{SERIAL_PORT}'")
        print(f"   Reason: {e}")
        print("\n💡 SOLUTION:")
        print("   1. Close Arduino IDE Serial Monitor")
        print("   2. Check if device is connected")
        print("   3. Try a different COM port")
        ser = None
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        ser = None
        return False

# --- Data Logging ---
def log_data(data_dict):
    """Appends a new reading to the CSV file."""
    file_exists = os.path.isfile(CSV_FILE)
    try:
        with open(CSV_FILE, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=data_dict.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_dict)
    except IOError as e:
        print(f"Error writing to CSV: {e}")

# --- Read Arduino Data ---
def read_arduino_data():
    """Read and parse data from Arduino"""
    global ser, last_data
    
    if not ser or not ser.is_open:
        if not init_serial():
            return last_data
    
    try:
        # Read line
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        
        if not line:
            last_data["error"] = "No data from Arduino"
            last_data["connected"] = False
            return last_data
        
        if ',' not in line:
            last_data["error"] = f"Invalid format: {line}"
            return last_data
        
        parts = line.split(',')
        
        if len(parts) >= 7:
            voltage = float(parts[0])
            current = float(parts[1])
            power = float(parts[2])
            temperature = float(parts[3])
            soc = float(parts[4])
            soh = float(parts[5])
            cycles = int(float(parts[6]))
            
            last_data = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "voltage": round(voltage, 2),
                "current": round(current, 2),
                "soc": round(soc, 2),
                "power": round(power, 2),
                "temperature": round(temperature, 2),
                "soh": round(soh, 2),
                "cycles": cycles,
                "connected": True,
                "error": None
            }
            
            # Log to CSV
            log_data(last_data)
            
            return last_data
        else:
            last_data["error"] = f"Expected 7 values, got {len(parts)}"
            return last_data
            
    except serial.SerialException as e:
        print(f"Serial error: {e}")
        ser = None
        last_data["connected"] = False
        last_data["error"] = "Connection lost"
        return last_data
    except ValueError as e:
        last_data["error"] = f"Parse error: {e}"
        return last_data
    except Exception as e:
        last_data["error"] = f"Unexpected error: {e}"
        return last_data

# --- Flask Routes ---

@app.route('/')
def index():
    """Serves the dashboard HTML - now using Flask's template system"""
    from flask import render_template
    try:
        # Flask automatically looks in the 'templates' folder
        return render_template('index2.html')
    except Exception as e:
        return f"""
        <html><body style="font-family: Arial; padding: 50px; background: #1a1a2e; color: #fff;">
        <h1>❌ Error: Could not load dashboard</h1>
        <p><strong>Error:</strong> {str(e)}</p>
        <p><strong>Solution:</strong> Make sure index2.html is in the 'templates' folder</p>
        <p>Your templates folder should contain:</p>
        <ul>
            <li>templates/index2.html</li>
        </ul>
        <a href="/" style="color: #00cdac;">Retry</a>
        </body></html>
        """, 404

@app.route('/data')
def get_data():
    """API endpoint for real-time data"""
    data = read_arduino_data()
    return jsonify(data)

@app.route('/download_report')
def download_report():
    """Generates PDF report"""
    if not os.path.exists(CSV_FILE):
        return """
        <html><body>
        <h1>Error</h1>
        <p>No data file found. Let the system run for a while.</p>
        <a href='/'>Go Back</a>
        </body></html>
        """, 404

    df = pd.read_csv(CSV_FILE)
    if df.empty:
        return """
        <html><body>
        <h1>Error</h1>
        <p>Data file is empty. No report to generate.</p>
        <a href='/'>Go Back</a>
        </body></html>
        """, 404

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Generate summary
    summary = {
        "avg_voltage": df['voltage'].mean(),
        "avg_current": df['current'].mean(),
        "avg_power": df['power'].mean(),
        "max_voltage": df['voltage'].max(),
        "latest_soc": df['soc'].iloc[-1],
        "estimated_soh": df['soh'].iloc[-1],
    }

    # Create chart
    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax2 = ax1.twinx()
    ax1.plot(df['timestamp'], df['voltage'], color='#6a11cb', label='Voltage (V)')
    ax2.plot(df['timestamp'], df['current'], color='#2575fc', label='Current (mA)')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Voltage (V)', color='#6a11cb')
    ax2.set_ylabel('Current (mA)', color='#2575fc')
    plt.title('Battery Voltage & Current Report')
    fig.legend(loc="upper right")
    fig.tight_layout()
    
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='PNG')
    img_buffer.seek(0)
    plt.close(fig)

    # Create PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 20)
    pdf.cell(0, 10, 'Battery Performance Report', 0, 1, 'C')
    pdf.set_font('Arial', '', 11)
    pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'C')
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Performance Summary', 0, 1)
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 8,
        f"  - Latest State of Charge (SoC): {summary['latest_soc']:.2f}%\n"
        f"  - Estimated State of Health (SoH): {summary['estimated_soh']:.2f}%\n"
        f"  - Average Voltage: {summary['avg_voltage']:.2f} V\n"
        f"  - Average Current: {summary['avg_current']:.2f} mA\n"
        f"  - Average Power: {summary['avg_power']:.2f} mW"
    )

    # Save temp image
    temp_img = 'temp_chart.png'
    with open(temp_img, 'wb') as f:
        f.write(img_buffer.getvalue())
    
    pdf.ln(10)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, 'Readings Chart', 0, 1)
    pdf.image(temp_img, x=10, w=190)
    
    # Clean up
    if os.path.exists(temp_img):
        os.remove(temp_img)

    return Response(
        pdf.output(dest='S').encode('latin-1'),
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment;filename=battery_report.pdf'}
    )

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  🔋 BATTERY MONITORING SYSTEM")
    print("="*60)
    
    # Initialize connection
    init_serial()
    
    print("\n🌐 Starting Flask server...")
    print("📊 Dashboard will be available at: http://127.0.0.1:5000")
    print("\n⚠️  IMPORTANT:")
    print("   - Make sure Arduino IDE Serial Monitor is CLOSED")
    print("   - Check that Arduino is sending data in format:")
    print("     voltage,current,power,temp,soc,soh,cycles")
    print("\n" + "="*60 + "\n")
    
    app.run(debug=True, port=5000, use_reloader=False)