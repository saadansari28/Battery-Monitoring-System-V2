import serial
import serial.tools.list_ports
import time
import csv
import os
from flask import Flask, jsonify, Response, render_template, render_template_string
from datetime import datetime
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for faster rendering
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
    """Generates a comprehensive PDF report with charts and data tables"""
    if not os.path.exists(CSV_FILE):
        return """<html><body style="font-family: Arial; padding: 50px; background: #1a1a2e; color: #fff;">
        <h1>❌ Error: No Data Available</h1>
        <p>No readings have been recorded yet. Please let the system run for at least 30 seconds.</p>
        <a href='/' style="color: #00cdac;">← Back to Dashboard</a>
        </body></html>""", 404

    try:
        df = pd.read_csv(CSV_FILE)
        if df.empty or len(df) < 2:
            return """<html><body style="font-family: Arial; padding: 50px; background: #1a1a2e; color: #fff;">
            <h1>❌ Error: Insufficient Data</h1>
            <p>Not enough data points to generate a report. Please wait for more readings.</p>
            <a href='/' style="color: #00cdac;">← Back to Dashboard</a>
            </body></html>""", 404

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Calculate summary statistics
        summary = {
            "soh": df['soh'].iloc[-1] if 'soh' in df.columns else 0,
            "total_cycles": int(df['cycles'].iloc[-1]) if 'cycles' in df.columns else 0,
            "avg_voltage": df['voltage'].mean(),
            "peak_current": df['current'].max(),
            "avg_temperature": df['temperature'].mean(),
            "latest_soc": df['soc'].iloc[-1] if 'soc' in df.columns else 0,
            "min_voltage": df['voltage'].min(),
            "max_voltage": df['voltage'].max(),
            "avg_power": df['power'].mean(),
            "total_readings": len(df)
        }

        # Create high-quality charts with optimized settings
        plt.style.use('default')
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), dpi=100)
        fig.patch.set_facecolor('white')
        
        # Chart 1: Voltage Over Time
        axes[0, 0].plot(df['timestamp'], df['voltage'], color='#6a11cb', linewidth=2)
        axes[0, 0].set_title('Voltage Over Time', fontsize=11, fontweight='bold')
        axes[0, 0].set_ylabel('Voltage (V)', fontsize=9)
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].tick_params(axis='x', rotation=45, labelsize=8)
        axes[0, 0].tick_params(axis='y', labelsize=8)
        
        # Chart 2: Current Over Time
        axes[0, 1].plot(df['timestamp'], df['current'], color='#2575fc', linewidth=2)
        axes[0, 1].set_title('Current Over Time', fontsize=11, fontweight='bold')
        axes[0, 1].set_ylabel('Current (mA)', fontsize=9)
        axes[0, 1].grid(True, alpha=0.3)
        axes[0, 1].tick_params(axis='x', rotation=45, labelsize=8)
        axes[0, 1].tick_params(axis='y', labelsize=8)
        
        # Chart 3: State of Charge Over Time
        axes[1, 0].plot(df['timestamp'], df['soc'], color='#fdcb6e', linewidth=2)
        axes[1, 0].set_title('State of Charge (SoC) Over Time', fontsize=11, fontweight='bold')
        axes[1, 0].set_ylabel('SoC (%)', fontsize=9)
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].tick_params(axis='x', rotation=45, labelsize=8)
        axes[1, 0].tick_params(axis='y', labelsize=8)
        
        # Chart 4: Temperature Over Time
        axes[1, 1].plot(df['timestamp'], df['temperature'], color='#e17055', linewidth=2)
        axes[1, 1].set_title('Temperature Over Time', fontsize=11, fontweight='bold')
        axes[1, 1].set_ylabel('Temperature (°C)', fontsize=9)
        axes[1, 1].grid(True, alpha=0.3)
        axes[1, 1].tick_params(axis='x', rotation=45, labelsize=8)
        axes[1, 1].tick_params(axis='y', labelsize=8)
        
        plt.tight_layout()
        
        # Save chart to buffer
        chart_buffer = io.BytesIO()
        plt.savefig(chart_buffer, format='PNG', bbox_inches='tight', dpi=150)
        chart_buffer.seek(0)
        plt.close(fig)

        # Create PDF with optimized settings
        pdf = FPDF('P', 'mm', 'A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Header with gradient effect (using colors)
        pdf.set_fill_color(26, 30, 46)  # Dark blue
        pdf.rect(0, 0, 210, 40, 'F')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Arial', 'B', 24)
        pdf.set_y(15)
        pdf.cell(0, 10, 'Battery Performance Report', 0, 1, 'C')
        pdf.set_font('Arial', '', 10)
        pdf.set_text_color(200, 200, 200)
        pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%d %B %Y at %H:%M:%S')}", 0, 1, 'C')
        
        # Reset text color
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(45)
        
        # Summary Cards Section
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(106, 17, 203)  # Purple
        pdf.cell(0, 10, 'Summary Overview', 0, 1, 'L')
        pdf.ln(2)
        
        # Determine health status and color based on SoH
        soh_value = summary['soh']
        if soh_value >= 80:
            health_status = "EXCELLENT"
            health_color = (46, 204, 113)  # Green
            health_bg = (232, 248, 237)    # Light green background
        elif soh_value >= 60:
            health_status = "GOOD"
            health_color = (52, 152, 219)  # Blue
            health_bg = (232, 243, 252)    # Light blue background
        elif soh_value >= 40:
            health_status = "AVERAGE"
            health_color = (241, 196, 15)  # Yellow/Orange
            health_bg = (254, 249, 231)    # Light yellow background
        else:
            health_status = "POOR"
            health_color = (231, 76, 60)   # Red
            health_bg = (254, 235, 235)    # Light red background
        
        # Draw prominent health status card at the top
        health_card_width = 190
        health_card_height = 28
        health_x = 10
        health_y = pdf.get_y()
        
        # Health card background with health color
        pdf.set_fill_color(*health_bg)
        pdf.rect(health_x, health_y, health_card_width, health_card_height, 'F')
        
        # Health card thick colored left border
        pdf.set_fill_color(*health_color)
        pdf.rect(health_x, health_y, 5, health_card_height, 'F')
        
        # Health status label
        pdf.set_xy(health_x + 10, health_y + 5)
        pdf.set_font('Arial', 'B', 12)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(60, 6, 'BATTERY HEALTH STATUS', 0, 0, 'L')
        
        # Health status value
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(*health_color)
        pdf.cell(60, 6, health_status, 0, 0, 'C')
        
        # SoH percentage
        pdf.set_font('Arial', 'B', 20)
        pdf.cell(60, 6, f"{soh_value:.1f}%", 0, 1, 'R')
        
        # Health description
        pdf.set_xy(health_x + 10, health_y + 14)
        pdf.set_font('Arial', '', 9)
        pdf.set_text_color(100, 100, 100)
        
        if soh_value >= 80:
            health_desc = "Battery is in excellent condition. Performance is optimal."
        elif soh_value >= 60:
            health_desc = "Battery is performing well with minor degradation."
        elif soh_value >= 40:
            health_desc = "Battery shows moderate wear. Monitor performance closely."
        else:
            health_desc = "Battery health is poor. Consider replacement soon."
        
        pdf.multi_cell(health_card_width - 20, 4, health_desc)
        
        pdf.set_y(health_y + health_card_height + 8)
        
        # Draw summary cards in a grid (other metrics)
        card_width = 60
        card_height = 22
        x_start = 10
        y_start = pdf.get_y()
        
        cards_data = [
            ("Total Cycles", f"{summary['total_cycles']}", (52, 152, 219)),
            ("Avg Voltage", f"{summary['avg_voltage']:.2f} V", (155, 89, 182)),
            ("Peak Current", f"{summary['peak_current']:.1f} mA", (231, 76, 60)),
            ("Avg Temperature", f"{summary['avg_temperature']:.1f} °C", (230, 126, 34)),
            ("Latest SoC", f"{summary['latest_soc']:.1f}%", (46, 204, 113)),
            ("Total Readings", f"{summary['total_readings']}", (52, 73, 94))
        ]
        
        for idx, (label, value, color) in enumerate(cards_data):
            row = idx // 3
            col = idx % 3
            x = x_start + (col * (card_width + 5))
            y = y_start + (row * (card_height + 5))
            
            # Draw card background
            pdf.set_fill_color(245, 247, 250)
            pdf.rect(x, y, card_width, card_height, 'F')
            
            # Draw colored top border
            pdf.set_fill_color(*color)
            pdf.rect(x, y, card_width, 3, 'F')
            
            # Card content
            pdf.set_xy(x + 3, y + 6)
            pdf.set_font('Arial', '', 8)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(card_width - 6, 4, label, 0, 1, 'C')
            
            pdf.set_x(x + 3)
            pdf.set_font('Arial', 'B', 14)
            pdf.set_text_color(*color)
            pdf.cell(card_width - 6, 8, value, 0, 1, 'C')
        
        pdf.set_y(y_start + (2 * (card_height + 5)) + 5)
        
        # Graphical Analysis Section
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(106, 17, 203)
        pdf.cell(0, 10, 'Graphical Analysis', 0, 1, 'L')
        pdf.ln(2)
        
        # Add the 4-panel chart
        temp_chart = 'temp_chart.png'
        with open(temp_chart, 'wb') as f:
            f.write(chart_buffer.getvalue())
        
        pdf.image(temp_chart, x=10, w=190)
        os.remove(temp_chart)
        
        # Add new page for data table
        pdf.add_page()
        
        # Data Table Section
        pdf.set_font('Arial', 'B', 16)
        pdf.set_text_color(106, 17, 203)
        pdf.cell(0, 10, 'Detailed Data Table', 0, 1, 'L')
        pdf.ln(2)
        
        # Table header
        pdf.set_font('Arial', 'B', 8)
        pdf.set_fill_color(106, 17, 203)
        pdf.set_text_color(255, 255, 255)
        
        col_widths = [38, 22, 22, 22, 28, 20, 20]
        headers = ['Timestamp', 'Voltage (V)', 'Current (mA)', 'Power (mW)', 'Temp (°C)', 'SoC (%)', 'SoH (%)']
        
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, 1, 0, 'C', True)
        pdf.ln()
        
        # Table rows (show last 30 entries for readability)
        pdf.set_font('Arial', '', 7)
        pdf.set_text_color(0, 0, 0)
        
        display_df = df.tail(30)  # Show last 30 readings
        
        for idx, row in display_df.iterrows():
            # Alternate row colors
            if idx % 2 == 0:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(255, 255, 255)
            
            timestamp = row['timestamp'].strftime('%d-%b %H:%M:%S')
            pdf.cell(col_widths[0], 6, timestamp, 1, 0, 'L', True)
            pdf.cell(col_widths[1], 6, f"{row['voltage']:.2f}", 1, 0, 'C', True)
            pdf.cell(col_widths[2], 6, f"{row['current']:.2f}", 1, 0, 'C', True)
            pdf.cell(col_widths[3], 6, f"{row['power']:.2f}", 1, 0, 'C', True)
            pdf.cell(col_widths[4], 6, f"{row['temperature']:.2f}", 1, 0, 'C', True)
            pdf.cell(col_widths[5], 6, f"{row['soc']:.1f}", 1, 0, 'C', True)
            pdf.cell(col_widths[6], 6, f"{row['soh']:.1f}", 1, 1, 'C', True)
        
        # Footer note
        pdf.ln(5)
        pdf.set_font('Arial', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 4, 
            f"Note: This report shows the last 30 readings out of {summary['total_readings']} total recorded measurements. "
            f"Data collection period: {df['timestamp'].min().strftime('%d %b %Y %H:%M')} to {df['timestamp'].max().strftime('%d %b %Y %H:%M')}"
        )
        
        # Generate PDF output
        pdf_output = pdf.output(dest='S')
        
        return Response(
            pdf_output.encode('latin-1') if isinstance(pdf_output, str) else pdf_output,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment;filename=battery_report.pdf'}
        )
        
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return f"""<html><body style="font-family: Arial; padding: 50px; background: #1a1a2e; color: #fff;">
        <h1>❌ Error Generating Report</h1>
        <p>An error occurred while creating the PDF: {str(e)}</p>
        <a href='/' style="color: #00cdac;">← Back to Dashboard</a>
        </body></html>""", 500

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