#MAIN

import pyvisa
import serial
import numpy as np
import matplotlib.pyplot as plt
import csv
import os
from datetime import datetime

##FUNCIONES
#CONECTAR EL OSCILOSCOPIO
def conectar_osciloscopio(recurso_visa=None,timeout=10000):

    rm = pyvisa.ResourceManager()

    resources = rm.list_resources()

    print("Instrumentos encontrados:")
    print(resources)

    if not resources:
        raise RuntimeError(
            "No se encontraron instrumentos VISA."
        )

    # Si no se especifica recurso VISA,
    # usa el primero encontrado
    if recurso_visa is None:
        recurso_visa = resources[0]

    scope = rm.open_resource(recurso_visa)

    scope.timeout = timeout

    print("\nConectado a:")
    print(scope.query("*IDN?"))

    return scope
#MEDIR CON EL OSCILOSCOPIO
def medir_pwm(scope,canal="CH1",start=1,stop=2500,graficar=True,guardar_excel=True,titulo="PWM"):

    # CONFIGURAR OSCILOSCOPIO
    comandos = [
        "HEADER OFF",
        f"DATA:SOURCE {canal}",
        "DATA:ENC RPB",
        "DATA:WIDTH 1",
        f"DATA:START {start}",
        f"DATA:STOP {stop}"
    ]

    for cmd in comandos:
        scope.write(cmd)

    # OBTENER PARÁMETROS
    ymult = scope.query_ascii_values("WFMPRE:YMULT?")[0]
    yzero = scope.query_ascii_values("WFMPRE:YZERO?")[0]
    yoff  = scope.query_ascii_values("WFMPRE:YOFF?")[0]
    xincr = scope.query_ascii_values("WFMPRE:XINCR?")[0]

    # LEER DATOS
    scope.write("CURVE?")
    raw = scope.read_raw()

    n_digits = int(chr(raw[1]))
    header_len = 2 + n_digits

    data = np.frombuffer(
        raw[header_len:-1],
        dtype=np.uint8
    )

    # CONVERTIR A VOLTAJE Y TIEMPO
    voltage = ((data.astype(float) - yoff) * ymult + yzero)
    time = np.arange(len(voltage)) * xincr

    metadata = {
        "YMULT": ymult,
        "YZERO": yzero,
        "YOFF": yoff,
        "XINCR": xincr
    }

    # CALCULAR PWM
    vmax, vmin = np.max(voltage), np.min(voltage)

    threshold = (vmax + vmin) / 2

    digital = voltage > threshold

    edges = np.diff(digital.astype(int))

    rising_edges = np.where(edges == 1)[0]
    falling_edges = np.where(edges == -1)[0]

    if len(rising_edges) < 2:
        raise RuntimeError(
            "No se detectó una señal PWM válida."
        )

    r1, r2 = rising_edges[:2]

    falling = falling_edges[
        (falling_edges > r1) &
        (falling_edges < r2)
    ]

    if len(falling) == 0:
        raise RuntimeError(
            "No se encontró flanco de bajada."
        )

    f1 = falling[0]

    # TIEMPOS
    periodo = time[r2] - time[r1]
    ton = time[f1] - time[r1]

    duty_cycle = (ton / periodo) * 100
    frecuencia = 1 / periodo

    # RESULTADOS
    # print("\n========== RESULTADOS PWM ==========")

    # print(f"Voltaje mínimo : {vmin:.3f} V")
    # print(f"Voltaje máximo : {vmax:.3f} V")
    # print(f"Frecuencia     : {frecuencia:.2f} Hz")
    # print(f"Periodo        : {periodo*1e3:.3f} ms")
    # print(f"Ton            : {ton*1e3:.3f} ms")
    # print(f"Ciclo trabajo  : {duty_cycle:.2f} %")

    # GUARDAR CSV
    archivo = None

    if guardar_excel:

        instrumento = scope.query("*IDN?").strip()

        filename = (
            f"osciloscopio_{canal}_"
            f"{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        with open(filename, "w", newline="") as f:

            writer = csv.writer(f)

            writer.writerow(["# Instrumento", instrumento])

            writer.writerow([
                "# Fecha",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])

            for key, value in metadata.items():
                writer.writerow([f"# {key}", value])

            writer.writerow([])
            writer.writerow(["Tiempo [s]", "Voltaje [V]"])

            writer.writerows([
                [f"{t:.10e}", f"{v:.6f}"]
                for t, v in zip(time, voltage)
            ])

        archivo = os.path.abspath(filename)

        print("\nCSV guardado en:")
        print(archivo)

    # GRAFICAR
    if graficar:

        if (time[-1] - time[0]) < 1:
            time_plot = time * 1e3
            xlabel = "Tiempo [ms]"
        else:
            time_plot = time
            xlabel = "Tiempo [s]"

        plt.figure(figsize=(11, 4))

        plt.plot(
            time_plot,
            voltage,
            linewidth=0.8
        )

        plt.xlabel(xlabel)
        plt.ylabel("Voltaje [V]")

        plt.title(
            f"{titulo} - {duty_cycle:.2f}%"
        )

        plt.grid(True)
        plt.tight_layout()
        plt.show()

    return duty_cycle, frecuencia,periodo,ton,vmax,vmin,archivo,time,voltage
#MEDIR CON EL MULTIMETRO
def obtener_medicion_fluke45(canal=1, puerto="COM6"):
    try:
        comando = b'VAL1?\n' if canal == 1 else b'VAL2?\r'
        with serial.Serial(
            port=puerto,
            baudrate=9600,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        ) as ser:
            ser.write(comando)
            respuesta = ser.readline().decode().strip()
            return float(respuesta) if respuesta else None
    except Exception as e:
        print("Error al leer:", e)
        return None

#Conectamos el osciloscopio
scope = conectar_osciloscopio()

##MAIN##
while True:
    duty_cycle,frecuencia,periodo,ton,vmax,vmin,archivo,time,voltage = medir_pwm(scope,canal="CH1",graficar=False,guardar_excel=False)
    Temperatura = obtener_medicion_fluke45()
    print(Temperatura, duty_cycle)

#Cerrar osciloscopio
scope.close()