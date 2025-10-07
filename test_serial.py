import serial

ser = serial.Serial('COM5', 9600, timeout=1)

while True:
    line = ser.readline().decode('utf-8').strip()
    if line:
        print("Arduino:", line)