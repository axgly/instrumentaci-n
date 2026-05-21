import serial
import time

arduino = serial.Serial('COM3', 9600, timeout=1)

time.sleep(2)

while True:

    linea = arduino.readline().decode('utf-8').strip()

    # Ignorar líneas vacías
    if linea == "":
        continue

    try:

        temp1, temp2 = linea.split(",")

        temp1 = float(temp1)
        temp2 = float(temp2)

        print("Sensor 1:", temp1,
              "Sensor 2:", temp2)

    except Exception as e:

        print("Error:", e)