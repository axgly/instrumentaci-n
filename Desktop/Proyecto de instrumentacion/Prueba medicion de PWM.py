#Prueba medicion de PWm
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
# CONFIGURAR CANAL
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
# ADQUIRIR DATOS
# =========================================================
def adquirir_datos(scope):

    ymult = scope.query_ascii_values("WFMPRE:YMULT?")[0]
    yzero = scope.query_ascii_values("WFMPRE:YZERO?")[0]
    yoff  = scope.query_ascii_values("WFMPRE:YOFF?")[0]
    xincr = scope.query_ascii_values("WFMPRE:XINCR?")[0]

    scope.write("CURVE?")
    raw = scope.read_raw()

    n_digits = int(chr(raw[1]))
    header_len = 2 + n_digits

    data = np.frombuffer(raw[header_len:-1],
                         dtype=np.uint8)

    voltage = (data.astype(float) - yoff) * ymult + yzero
    time = np.arange(len(voltage)) * xincr

    metadata = {
        "YMULT": ymult,
        "YZERO": yzero,
        "YOFF": yoff,
        "XINCR": xincr
    }

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

    print("CSV guardado:")
    print(os.path.abspath(filename))

    return filename


# =========================================================
# GRAFICAR
# =========================================================
def graficar(time, voltage, titulo="PWM"):

    t_range = time[-1] - time[0]

    if t_range < 1:
        time_plot = time * 1e3
        xlabel = "Tiempo [ms]"
    else:
        time_plot = time
        xlabel = "Tiempo [s]"

    plt.figure(figsize=(11,4))

    plt.plot(time_plot,
             voltage,
             linewidth=0.8)

    plt.xlabel(xlabel)
    plt.ylabel("Voltaje [V]")
    plt.title(titulo)

    plt.grid(True)

    plt.tight_layout()
    plt.show()


# =========================================================
# MEDIR CICLO DE TRABAJO PWM
# =========================================================
def medir_pwm(canal="CH1",
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

        # =================================================
        # CALCULAR UMBRAL
        # =================================================
        vmax = np.max(voltage)
        vmin = np.min(voltage)

        threshold = (vmax + vmin) / 2

        # =================================================
        # CONVERTIR A DIGITAL
        # =================================================
        digital = voltage > threshold

        # =================================================
        # DETECTAR FLANCOS
        # =================================================
        edges = np.diff(digital.astype(int))

        rising_edges = np.where(edges == 1)[0]
        falling_edges = np.where(edges == -1)[0]

        if len(rising_edges) < 2:
            raise RuntimeError("No se detectó una señal PWM válida.")

        # =================================================
        # TOMAR PRIMER PERIODO
        # =================================================
        r1 = rising_edges[0]
        r2 = rising_edges[1]

        # buscar flanco de bajada entre ellos
        falling = falling_edges[
            (falling_edges > r1) &
            (falling_edges < r2)
        ]

        if len(falling) == 0:
            raise RuntimeError("No se encontró flanco de bajada.")

        f1 = falling[0]

        # =================================================
        # TIEMPOS
        # =================================================
        t_r1 = time[r1]
        t_r2 = time[r2]
        t_f1 = time[f1]

        periodo = t_r2 - t_r1
        ton = t_f1 - t_r1

        duty_cycle = (ton / periodo) * 100
        frecuencia = 1 / periodo

        # =================================================
        # RESULTADOS
        # =================================================
        print("\n========== RESULTADOS PWM ==========")

        print(f"Voltaje mínimo : {vmin:.3f} V")
        print(f"Voltaje máximo : {vmax:.3f} V")

        print(f"Frecuencia     : {frecuencia:.2f} Hz")
        print(f"Periodo        : {periodo*1e3:.3f} ms")
        print(f"Ton             : {ton*1e3:.3f} ms")
        print(f"Ciclo trabajo  : {duty_cycle:.2f} %")

        # =================================================
        # GUARDAR
        # =================================================
        archivo = guardar_csv(time,
                              voltage,
                              metadata,
                              instrumento,
                              canal)

    finally:
        scope.close()

    # =====================================================
    # GRAFICAR
    # =====================================================
    graficar(time,
             voltage,
             titulo=f"PWM {duty_cycle:.2f}%")

    return {
        "duty_cycle": duty_cycle,
        "frecuencia": frecuencia,
        "periodo": periodo,
        "ton": ton,
        "archivo": archivo
    }


# =========================================================
# USAR
# =========================================================
resultado = medir_pwm("CH1")