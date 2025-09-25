from flask import Flask, jsonify, render_template
import serial
import time
import threading
from datetime import datetime

app = Flask(__name__)

# Global variables
latest_data = {
    "voltage": 0.0,
    "current": 0.0,
    "temperature": 0.0,
    "soc": 0.0,
    "power": 0.0,
    "energy": 0.0,
    "cycles": 0,
    "soh": 95.0,
    "timestamp": "Never"
}

ser = None
is_connected = False

def init_serial():
    global ser, is_connected
    try:
        ser = serial.Serial('COM5', 9600, timeout=1)
        time.sleep(2)
        is_connected = True
        print("✅ Connected to Arduino on COM5")
    except Exception as e:
        print(f"❌ Could not connect to COM5: {e}")
        ser = None
        is_connected = False

def read_serial():
    global latest_data, is_connected
    while True:
        if ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8').strip()
                    if line:
                        print(f"📡 Received: {line}")
                        parts = line.split(',')
                        if len(parts) >= 7:
                            latest_data.update({
                                "voltage": float(parts[0]),
                                "current": float(parts[1]),
                                "temperature": float(parts[2]),
                                "soc": float(parts[3]),
                                "power": float(parts[4]),
                                "energy": float(parts[5]),
                                "cycles": int(float(parts[6])),
                                "soh": 95.0,
                                "timestamp": datetime.now().strftime("%H:%M:%S")
                            })
                            print(f"✅ Updated data at {latest_data['timestamp']}")
            except Exception as e:
                print(f"⚠️ Error reading serial: {e}")
                is_connected = False
        else:
            # Try to reconnect every 5 seconds
            time.sleep(5)
            init_serial()

@app.route('/')
def index():
    return render_template('index2.html')

@app.route('/data')
def get_data():
    # Add connection status to the response
    data_with_status = latest_data.copy()
    data_with_status['connected'] = is_connected
    return jsonify(data_with_status)

if __name__ == '__main__':
    print("🚀 Starting Battery Monitoring System...")
    init_serial()
    
    # Start serial reading thread
    if ser:
        serial_thread = threading.Thread(target=read_serial, daemon=True)
        serial_thread.start()
        print("📊 Serial reading thread started")
    
    print("🌐 Starting Flask server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)