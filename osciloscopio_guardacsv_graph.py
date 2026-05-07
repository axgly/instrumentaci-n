import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import csv
import os
from datetime import datetime

# --- CONFIGURACIÓN DE LA CONEXIÓN ---
rm = pyvisa.ResourceManager()
resources = rm.list_resources()
print("Instrumentos encontrados:", resources)

if not resources:
    raise RuntimeError("No se encontraron instrumentos VISA.")

scope = rm.open_resource(resources[0])
scope.timeout = 10000  # ms

# --- NOMBRE DE ARCHIVO CON TIMESTAMP ---
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
csv_filename = f"osciloscopio_CH1_{timestamp}.csv"

try:
    # --- IDENTIFICACIÓN ---
    idn = scope.query("*IDN?")
    print("Conectado a:", idn)

    # --- CONFIGURACIÓN DEL CANAL Y FORMATO DE DATOS ---
    scope.write("DATA:SOURCE CH1")
    scope.write("DATA:ENC RPB")
    scope.write("DATA:WIDTH 1")

    # --- OBTENER PARÁMETROS DE ESCALA ---
    ymult = float(scope.query("WFMPRE:YMULT?"))
    yzero = float(scope.query("WFMPRE:YZERO?"))
    yoff  = float(scope.query("WFMPRE:YOFF?"))
    xincr = float(scope.query("WFMPRE:XINCR?"))

    # --- SOLICITAR DATOS BINARIOS ---
    scope.write("CURVE?")
    raw = scope.read_raw()

    # Parseo del encabezado IEEE 488.2
    n_digits = int(chr(raw[1]))
    header_len = 2 + n_digits
    data = np.frombuffer(raw[header_len:-1], dtype=np.uint8)

    # --- CONVERTIR A VOLTAJE Y TIEMPO ---
    voltage = (data.astype(float) - yoff) * ymult + yzero
    time    = np.arange(len(voltage)) * xincr

    print(f"Datos recibidos: {len(voltage)} puntos")

    # =========================================================
    # --- GUARDAR EN CSV ---
    # =========================================================
    with open(csv_filename, mode="w", newline="") as f:
        writer = csv.writer(f)
        # Encabezado con metadatos del osciloscopio
        writer.writerow(["# Instrumento", idn.strip()])
        writer.writerow(["# Fecha", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow(["# YMULT", ymult])
        writer.writerow(["# YZERO", yzero])
        writer.writerow(["# YOFF",  yoff])
        writer.writerow(["# XINCR", xincr])
        writer.writerow([])                        # línea en blanco
        writer.writerow(["Tiempo [s]", "Voltaje [V]"])  # columnas
        for t, v in zip(time, voltage):
            writer.writerow([f"{t:.10e}", f"{v:.6f}"])

    print(f"Datos guardados en: {os.path.abspath(csv_filename)}")

finally:
    scope.close()

# =========================================================
# --- GRAFICAR DESDE EL CSV ---
# =========================================================
def graficar_desde_csv(filepath):
    time_data    = []
    voltage_data = []
    metadata     = {}

    with open(filepath, mode="r") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            # Leer metadatos (líneas que empiezan con #)
            if row[0].startswith("#"):
                key = row[0].replace("#", "").strip()
                val = row[1].strip() if len(row) > 1 else ""
                metadata[key] = val
                continue
            # Saltar encabezado de columnas
            if row[0] == "Tiempo [s]":
                continue
            # Leer datos numéricos
            try:
                time_data.append(float(row[0]))
                voltage_data.append(float(row[1]))
            except ValueError:
                continue

    time_arr    = np.array(time_data)
    voltage_arr = np.array(voltage_data)

    # Info para el título
    instrumento = metadata.get("Instrumento", "Osciloscopio")
    fecha       = metadata.get("Fecha", "")

    # Convertir tiempo a ms si el rango es pequeño
    t_range = time_arr[-1] - time_arr[0]
    if t_range < 1:
        time_plot  = time_arr * 1e3
        xlabel_str = "Tiempo [ms]"
    else:
        time_plot  = time_arr
        xlabel_str = "Tiempo [s]"

    plt.figure(figsize=(11, 4))
    plt.plot(time_plot, voltage_arr, color="royalblue", linewidth=0.8)
    plt.title(f"CH1 – {instrumento}\n{fecha}", fontsize=10)
    plt.xlabel(xlabel_str)
    plt.ylabel("Voltaje [V]")
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()

    # Guardar la gráfica como imagen junto al CSV
    img_filename = filepath.replace(".csv", ".png")
    plt.savefig(img_filename, dpi=150)
    print(f"Gráfica guardada en: {os.path.abspath(img_filename)}")
    plt.show()

graficar_desde_csv(csv_filename)