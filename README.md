🔋 Advanced Battery Monitoring System with PDF Reporting
This project provides a real-time web dashboard to monitor key performance metrics of a battery connected to an Arduino. It features a modern, responsive interface and includes a powerful new feature to generate and download detailed PDF performance reports.

(To add a real screenshot: take a picture of your dashboard, upload it to your GitHub repository, and replace the link above with the link to your image.)

✨ Key Features
Real-Time Monitoring: View live data for Voltage, Current, Power, and State of Charge (SoC).

Dynamic Charts: Visualize performance trends with live-updating charts for all key metrics.

PDF Report Generation: Download a comprehensive PDF report containing a performance summary, a detailed data log, and a readings chart.

Battery Health Analysis: The PDF report includes a user-friendly qualitative assessment of the battery's health (e.g., "Excellent," "Good," "Average").

Clean & Modern UI: A sleek, dark-themed dashboard that is fully responsive and looks great on any device.

Easy Setup: A straightforward setup process using Python (Flask) for the back-end and standard HTML/CSS/JS for the front-end.

🛠️ Getting Started
Follow these instructions to get the project up and running on your local machine.

Prerequisites
Hardware
An Arduino board (e.g., Arduino Uno, Nano, or Mega)

Battery to be monitored

Appropriate sensors to measure voltage and current (e.g., INA219)

Jumper wires and a breadboard

Software
Python 3.8+

Git

Arduino IDE

Step 1: Clone the Repository
First, clone this repository to your local machine using Git.

git clone [https://github.com/saadansari28/Battery-Monitoring-System-V2.git](https://github.com/saadansari28/Battery-Monitoring-System-V2.git)
cd Battery-Monitoring-System-V2

(Replace Battery-Monitoring-System-V2 with the actual name of your repository)

Step 2: Set Up the Python Environment
It is highly recommended to use a virtual environment to keep project dependencies isolated.

Create a virtual environment:

python -m venv venv

Activate the virtual environment:

On Windows:

.\venv\Scripts\activate

On macOS/Linux:

source venv/bin/activate

You should see (venv) at the beginning of your terminal prompt.

Install the required libraries:

pip install flask pyserial pandas matplotlib fpdf2

Step 3: Configure the Arduino
Open the batttery.ino file in the Arduino IDE.

Make sure you have any necessary libraries for your sensors installed (e.g., Adafruit INA219 library).

Upload the sketch to your Arduino board.

⚙️ Configuration
Before running the application, you must configure the correct serial port for your Arduino.

Find your Arduino's port:

Open the Arduino IDE.

Go to Tools -> Port. The port with your Arduino model name next to it is the correct one (e.g., COM5, /dev/ttyUSB0).

Update the app.py file:

Open the app.py file in a text editor.

Find the line SERIAL_PORT = 'COM3'

Change 'COM3' to the correct port you found in the previous step. For example:

SERIAL_PORT = 'COM5'

Save the file.

🚀 Running the Application
With your virtual environment activated and the serial port configured, start the Flask server.

python app.py

You should see output indicating the server is running on http://127.0.0.1:5000.

How to Use
Open your web browser and navigate to http://127.0.0.1:5000.

The dashboard will load and start displaying real-time data from the Arduino.

Let the application run for a minute to collect some data.

Click the "Download PDF Report" button at the bottom of the page to download your detailed performance report.

📂 Project Structure
.
├── templates/
│   └── index2.html       # The main dashboard HTML file
├── app.py                # The main Flask application (back-end logic)
├── batttery.ino          # The Arduino sketch
├── README.md             # This file
└── .gitignore            # Tells Git which files to ignore
