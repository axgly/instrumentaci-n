import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import csv
import os
from datetime import datetime

# =========================================================
# CONECTAR OSCILOSCOPIO
# =========================================================
def conectar_osciloscopio():

    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()

    print("Instrumentos encontrados:", resources)

    if not resources:
        raise RuntimeError("No se encontraron instrumentos VISA.")

    scope = rm.open_resource(resources[0])
    scope.timeout = 10000

    print("Conectado a:", scope.query("*IDN?"))

    return scope

# =========================================================
# CONFIGURAR OSCILOSCOPIO
# =========================================================
def configurar_canal(scope,
                      canal="CH1",
                      start=1,
                      stop=2500):

    scope.write("HEADER OFF")
    scope.write(f"DATA:SOURCE {canal}")
    scope.write("DATA:ENC RPB")
    scope.write("DATA:WIDTH 1")
    scope.write(f"DATA:START {start}")
    scope.write(f"DATA:STOP {stop}")

# =========================================================
# LEER DATOS
# =========================================================
def adquirir_datos(scope):

    ymult = scope.query_ascii_values("WFMPRE:YMULT?")[0]
    yzero = scope.query_ascii_values("WFMPRE:YZERO?")[0]
    yoff  = scope.query_ascii_values("WFMPRE:YOFF?")[0]
    xincr = scope.query_ascii_values("WFMPRE:XINCR?")[0]

    scope.write("CURVE?")
    raw = scope.read_raw()

    n_digits  = int(chr(raw[1]))
    header_len = 2 + n_digits

    data = np.frombuffer(raw[header_len:-1], dtype=np.uint8)

    voltage = (data.astype(float) - yoff) * ymult + yzero
    time = np.arange(len(voltage)) * xincr

    metadata = {
        "YMULT": ymult,
        "YZERO": yzero,
        "YOFF": yoff,
        "XINCR": xincr
    }

    print(f"Datos recibidos: {len(voltage)} puntos")

    return time, voltage, metadata

# =========================================================
# GUARDAR CSV
# =========================================================
def guardar_csv(time,
                voltage,
                metadata,
                instrumento="Osciloscopio",
                canal="CH1"):

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"osciloscopio_{canal}_{timestamp}.csv"

    with open(filename, mode="w", newline="") as f:

        writer = csv.writer(f)

        writer.writerow(["# Instrumento", instrumento])
        writer.writerow(["# Fecha",
                         datetime.now().strftime("%Y-%m-%d %H:%M:%S")])

        for key, value in metadata.items():
            writer.writerow([f"# {key}", value])

        writer.writerow([])
        writer.writerow(["Tiempo [s]", "Voltaje [V]"])

        for t, v in zip(time, voltage):
            writer.writerow([f"{t:.10e}", f"{v:.6f}"])

    print("Datos guardados en:")
    print(os.path.abspath(filename))

    return filename

# =========================================================
# GRAFICAR CSV
# =========================================================
def graficar_csv(filepath):

    time_data = []
    voltage_data = []

    with open(filepath, mode="r") as f:

        reader = csv.reader(f)

        for row in reader:

            if not row:
                continue

            if row[0].startswith("#"):
                continue

            if row[0] == "Tiempo [s]":
                continue

            try:
                time_data.append(float(row[0]))
                voltage_data.append(float(row[1]))
            except:
                pass

    time_arr = np.array(time_data)
    voltage_arr = np.array(voltage_data)

    t_range = time_arr[-1] - time_arr[0]

    if t_range < 1:
        time_plot = time_arr * 1e3
        xlabel = "Tiempo [ms]"
    else:
        time_plot = time_arr
        xlabel = "Tiempo [s]"

    plt.figure(figsize=(11,4))

    plt.plot(time_plot,
             voltage_arr,
             linewidth=0.8)

    plt.xlabel(xlabel)
    plt.ylabel("Voltaje [V]")
    plt.title(filepath)
    plt.grid(True)

    plt.tight_layout()

    img_name = filepath.replace(".csv", ".png")

    plt.savefig(img_name, dpi=150)

    print("Gráfica guardada en:")
    print(os.path.abspath(img_name))

    plt.show()

# =========================================================
# FUNCIÓN PRINCIPAL
# =========================================================
def medir(canal="CH1",
          start=1,
          stop=2500):

    scope = conectar_osciloscopio()

    try:

        configurar_canal(scope,
                          canal=canal,
                          start=start,
                          stop=stop)

        time, voltage, metadata = adquirir_datos(scope)

        instrumento = scope.query("*IDN?").strip()

        archivo = guardar_csv(time,
                              voltage,
                              metadata,
                              instrumento,
                              canal)

    finally:
        scope.close()

    graficar_csv(archivo)

    return archivo

# =========================================================
# USAR
# =========================================================
medir()