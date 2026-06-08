"""
pipeline.py
-----------
Pipeline de datos Bronze → Silver → Gold usando:
- Prefect: para orquestar las tareas en orden automático
- DuckDB:  para guardar los datos en capas (bronze, silver, gold)
- yfinance: para descargar precios históricos

Nuevas funciones:
- declarar_var_semanal(): calcula y guarda la declaración del VaR semanal
- monitorear_var_semanal(): descarga precios reales y verifica si el VaR se violó
"""

import os
import time
import duckdb
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from prefect import flow, task

# ─── Ruta de la base de datos DuckDB ─────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "data", "portafolio.duckdb")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    return con


# ─── TAREA 1: BRONZE ──────────────────────────────────────────────────────────
@task(name="Bronze - Descargar precios", log_prints=True)
def bronze_descargar_precios(tickers: list, periodo_dias: int = 365) -> pd.DataFrame:
    print(f"[BRONZE] Descargando {tickers} — últimos {periodo_dias} días...")

    fecha_fin    = datetime.today()
    fecha_inicio = fecha_fin - timedelta(days=periodo_dias)
    todos = []

    try:
        raw = yf.download(
            tickers,
            start=fecha_inicio.strftime("%Y-%m-%d"),
            end=fecha_fin.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )

        for ticker in tickers:
            try:
                df_t = raw[["Close"]].copy() if len(tickers) == 1 else raw[ticker][["Close"]].copy()
                df_t.columns = ["close"]
                df_t = df_t.dropna()
                if df_t.empty:
                    print(f"[BRONZE] Sin datos para {ticker}")
                    continue
                df_t = df_t.reset_index()
                df_t.rename(columns={"Date": "fecha", "Datetime": "fecha"}, inplace=True)
                df_t["ticker"]        = ticker
                df_t["descargado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                df_t["fecha"]         = df_t["fecha"].astype(str)
                todos.append(df_t)
                print(f"[BRONZE] ✓ {ticker}: {len(df_t)} registros")
            except Exception as e:
                print(f"[BRONZE] Error procesando {ticker}: {e}")

    except Exception as e:
        print(f"[BRONZE] Descarga masiva falló: {e}. Intentando uno por uno...")
        for ticker in tickers:
            try:
                time.sleep(3)
                datos = yf.download(ticker,
                    start=fecha_inicio.strftime("%Y-%m-%d"),
                    end=fecha_fin.strftime("%Y-%m-%d"),
                    progress=False, auto_adjust=True)
                if datos.empty:
                    continue
                datos = datos[["Close"]].copy()
                datos.columns = ["close"]
                datos = datos.reset_index()
                datos.rename(columns={"Date": "fecha"}, inplace=True)
                datos["ticker"]        = ticker
                datos["descargado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                datos["fecha"]         = datos["fecha"].astype(str)
                todos.append(datos)
                print(f"[BRONZE] ✓ {ticker}: {len(datos)} registros")
            except Exception as e2:
                print(f"[BRONZE] Error descargando {ticker}: {e2}")

    if not todos:
        print("[BRONZE] ⚠ No se pudo descargar ningún ticker.")
        return pd.DataFrame()

    df_bronze = pd.concat(todos, ignore_index=True)
    con = get_connection()
    con.register("_bronze", df_bronze)
    con.execute("CREATE OR REPLACE TABLE bronze.precios AS SELECT * FROM _bronze")
    con.unregister("_bronze")
    con.close()
    print(f"[BRONZE] ✓ {len(df_bronze)} registros guardados en bronze.precios")
    return df_bronze


# ─── TAREA 2: SILVER ─────────────────────────────────────────────────────────
@task(name="Silver - Limpiar y calcular retornos", log_prints=True)
def silver_limpiar_y_retornos() -> pd.DataFrame:
    print("[SILVER] Limpiando datos y calculando retornos logarítmicos...")
    con = get_connection()
    try:
        df = con.table("bronze.precios").df()
    except Exception as e:
        con.close()
        print(f"[SILVER] ⚠ No se encontró bronze.precios: {e}")
        return pd.DataFrame()
    con.close()

    if df.empty:
        return pd.DataFrame()

    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["ticker", "fecha"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df["retorno_log"] = df.groupby("ticker")["close"].transform(
        lambda x: np.log(x / x.shift(1))
    )
    df = df.dropna(subset=["retorno_log"])
    df["procesado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["fecha"]        = df["fecha"].astype(str)

    con = get_connection()
    con.register("_silver", df)
    con.execute("CREATE OR REPLACE TABLE silver.precios AS SELECT * FROM _silver")
    con.unregister("_silver")
    con.close()
    print(f"[SILVER] ✓ {len(df)} registros guardados en silver.precios")
    return df


# ─── TAREA 3: GOLD ───────────────────────────────────────────────────────────
@task(name="Gold - Calcular VaR y CVaR", log_prints=True)
def gold_calcular_var(
    pesos: dict,
    nivel_confianza: float = 0.95,
    valor_portafolio: float = 100_000,
) -> dict:
    print(f"[GOLD] Calculando VaR al {nivel_confianza:.0%}...")
    con = get_connection()
    try:
        df = con.table("silver.precios").df()
    except Exception as e:
        con.close()
        return {"error": f"No hay datos en silver.precios: {e}"}
    con.close()

    if df.empty:
        return {"error": "Silver está vacío."}

    df["fecha"] = pd.to_datetime(df["fecha"])
    tabla = df.pivot_table(index="fecha", columns="ticker", values="retorno_log")
    tabla = tabla.dropna()

    tickers_ok = [t for t in pesos if t in tabla.columns]
    if not tickers_ok:
        return {"error": f"Tickers no encontrados. Disponibles: {tabla.columns.tolist()}"}

    tabla = tabla[tickers_ok]
    pesos_arr = np.array([pesos[t] for t in tickers_ok])
    pesos_arr = pesos_arr / pesos_arr.sum()

    retornos = tabla.values @ pesos_arr
    percentil   = (1 - nivel_confianza) * 100
    var_pct     = np.percentile(retornos, percentil)
    var_dinero  = abs(var_pct) * valor_portafolio
    cvar_pct    = retornos[retornos <= var_pct].mean()
    cvar_dinero = abs(cvar_pct) * valor_portafolio

    resultado = {
        "tickers":               tickers_ok,
        "pesos":                 dict(zip(tickers_ok, pesos_arr)),
        "nivel_confianza":       nivel_confianza,
        "var_pct":               var_pct,
        "var_dinero":            var_dinero,
        "cvar_pct":              cvar_pct,
        "cvar_dinero":           cvar_dinero,
        "valor_portafolio":      valor_portafolio,
        "num_observaciones":     len(retornos),
        "retornos_portafolio":   retornos,
        "fechas":                tabla.index.tolist(),
        "retornos_individuales": {t: tabla[t].values for t in tickers_ok},
    }

    resumen = pd.DataFrame([{
        "calculado_en":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tickers":         str(tickers_ok),
        "nivel_confianza": nivel_confianza,
        "var_pct":         round(var_pct, 6),
        "var_dinero":      round(var_dinero, 2),
        "cvar_pct":        round(cvar_pct, 6),
        "cvar_dinero":     round(cvar_dinero, 2),
        "valor_portafolio": valor_portafolio,
    }])

    con = get_connection()
    con.register("_gold", resumen)
    try:
        con.execute("INSERT INTO gold.resultados SELECT * FROM _gold")
    except Exception:
        con.execute("CREATE TABLE gold.resultados AS SELECT * FROM _gold")
    con.unregister("_gold")
    con.close()

    print(f"[GOLD] ✓ VaR={abs(var_pct):.2%} (${var_dinero:,.2f}) | CVaR={abs(cvar_pct):.2%} (${cvar_dinero:,.2f})")
    return resultado


# ─── FLOW PRINCIPAL ───────────────────────────────────────────────────────────
@flow(name="Pipeline VaR — Bronze→Silver→Gold", log_prints=True)
def ejecutar_pipeline_completo(
    tickers:          list,
    pesos:            dict,
    nivel_confianza:  float,
    valor_portafolio: float,
    periodo_dias:     int = 365,
) -> dict:
    bronze_descargar_precios(tickers, periodo_dias)
    silver_limpiar_y_retornos()
    resultado = gold_calcular_var(pesos, nivel_confianza, valor_portafolio)
    return resultado


# ─── VaR SEMANAL: DECLARACIÓN ─────────────────────────────────────────────────

def declarar_var_semanal(
    pesos:            dict,
    nivel_confianza:  float = 0.95,
    valor_portafolio: float = 100_000,
    intento:          int   = 1,
    periodo_dias:     int   = 756,   # 3 años de historia por defecto
) -> dict:
    """
    Calcula el VaR semanal del portafolio (escala VaR diario × √5),
    guarda la declaración en gold.declaraciones_semanales y retorna el resultado.

    La 'fecha_inicio' es el próximo lunes (o hoy si es lunes),
    la 'fecha_fin' es el viernes de esa misma semana.
    """
    tickers = list(pesos.keys())
    print(f"[SEMANAL] Descargando datos para {tickers} ({periodo_dias} días de historia)...")

    # ── Descargar datos históricos directamente (sin Prefect para simplificar) ──
    fecha_fin_hist    = datetime.today()
    fecha_inicio_hist = fecha_fin_hist - timedelta(days=periodo_dias)
    todos = []

    try:
        raw = yf.download(
            tickers,
            start=fecha_inicio_hist.strftime("%Y-%m-%d"),
            end=fecha_fin_hist.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
        for ticker in tickers:
            try:
                df_t = raw[["Close"]].copy() if len(tickers) == 1 else raw[ticker][["Close"]].copy()
                df_t.columns = ["close"]
                df_t = df_t.dropna().reset_index()
                df_t.rename(columns={"Date": "fecha"}, inplace=True)
                df_t["ticker"] = ticker
                todos.append(df_t)
            except Exception as e:
                print(f"[SEMANAL] Error con {ticker}: {e}")
    except Exception as e:
        return {"error": f"No se pudieron descargar datos: {e}"}

    if not todos:
        return {"error": "No se obtuvieron datos históricos."}

    df = pd.concat(todos, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["ticker", "fecha"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])
    df["retorno_log"] = df.groupby("ticker")["close"].transform(
        lambda x: np.log(x / x.shift(1))
    )
    df = df.dropna(subset=["retorno_log"])

    # ── Pivote y cálculo ──────────────────────────────────────────────────────
    tabla = df.pivot_table(index="fecha", columns="ticker", values="retorno_log").dropna()
    tickers_ok = [t for t in pesos if t in tabla.columns]
    if not tickers_ok:
        return {"error": f"Tickers no encontrados en datos. Disponibles: {tabla.columns.tolist()}"}

    tabla = tabla[tickers_ok]
    pesos_arr = np.array([pesos[t] for t in tickers_ok])
    pesos_arr = pesos_arr / pesos_arr.sum()

    retornos = tabla.values @ pesos_arr
    percentil    = (1 - nivel_confianza) * 100
    var_diario   = np.percentile(retornos, percentil)       # negativo
    cvar_diario  = retornos[retornos <= var_diario].mean()  # negativo

    # Escalar a semanal: VaR_semanal = VaR_diario × √5  (Basel II/III)
    var_semanal  = var_diario  * np.sqrt(5)
    cvar_semanal = cvar_diario * np.sqrt(5)

    var_semanal_usd  = abs(var_semanal)  * valor_portafolio
    cvar_semanal_usd = abs(cvar_semanal) * valor_portafolio

    # ── Fechas de la semana declarada ─────────────────────────────────────────
    hoy = datetime.today()
    # Siguiente lunes (o hoy si es lunes)
    dias_hasta_lunes = (7 - hoy.weekday()) % 7
    if dias_hasta_lunes == 0:
        lunes = hoy
    else:
        lunes = hoy + timedelta(days=dias_hasta_lunes)
    viernes = lunes + timedelta(days=4)

    fecha_inicio_str = lunes.strftime("%Y-%m-%d")
    fecha_fin_str    = viernes.strftime("%Y-%m-%d")

    resultado = {
        "tickers":           tickers_ok,
        "pesos":             dict(zip(tickers_ok, pesos_arr)),
        "nivel_confianza":   nivel_confianza,
        "var_diario_pct":    var_diario,
        "var_semanal_pct":   var_semanal,
        "var_semanal_usd":   var_semanal_usd,
        "cvar_semanal_pct":  cvar_semanal,
        "cvar_semanal_usd":  cvar_semanal_usd,
        "valor_portafolio":  valor_portafolio,
        "num_observaciones": len(retornos),
        "fecha_inicio":      fecha_inicio_str,
        "fecha_fin":         fecha_fin_str,
        "intento":           intento,
        "declarado_en":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # ── Guardar en DuckDB ─────────────────────────────────────────────────────
    decl_df = pd.DataFrame([{
        "intento":           intento,
        "declarado_en":      resultado["declarado_en"],
        "tickers":           str(tickers_ok),
        "pesos":             str(dict(zip(tickers_ok, pesos_arr.tolist()))),
        "nivel_confianza":   nivel_confianza,
        "valor_portafolio":  valor_portafolio,
        "var_diario_pct":    round(var_diario,      6),
        "var_semanal_pct":   round(var_semanal,     6),
        "var_semanal_usd":   round(var_semanal_usd, 2),
        "cvar_semanal_pct":  round(cvar_semanal,    6),
        "cvar_semanal_usd":  round(cvar_semanal_usd,2),
        "fecha_inicio":      fecha_inicio_str,
        "fecha_fin":         fecha_fin_str,
        "estado":            "EN_CURSO",
    }])

    con = get_connection()
    con.register("_decl", decl_df)
    try:
        # Si ya existe una declaración para este intento, la reemplaza
        try:
            con.execute(f"DELETE FROM gold.declaraciones_semanales WHERE intento = {intento}")
        except Exception:
            pass
        try:
            con.execute("INSERT INTO gold.declaraciones_semanales SELECT * FROM _decl")
        except Exception:
            con.execute("CREATE TABLE gold.declaraciones_semanales AS SELECT * FROM _decl")
    finally:
        con.unregister("_decl")
        con.close()

    print(f"[SEMANAL] ✓ Declaración guardada — Intento {intento} | VaR semanal: {abs(var_semanal):.3%} (${var_semanal_usd:,.2f})")
    print(f"[SEMANAL]   Semana: {fecha_inicio_str} → {fecha_fin_str}")
    return resultado


# ─── VaR SEMANAL: MONITOR ─────────────────────────────────────────────────────

def monitorear_var_semanal(intento: int = 1) -> dict:
    """
    Lee la declaración guardada, descarga los precios reales de la semana
    y calcula si la pérdida acumulada superó el VaR declarado en algún día.

    Retorna:
        estado: "EN_CURSO" | "RESPETADO" | "VIOLADO"
        dias_monitoreados: int
        violaciones: int
        retornos_acumulados: list[float]  (pérdida acumulada diaria, como fracción)
        fechas_reales: list[str]
    """
    # ── Leer declaración ──────────────────────────────────────────────────────
    con = get_connection()
    try:
        decl = con.execute(
            f"SELECT * FROM gold.declaraciones_semanales WHERE intento = {intento}"
        ).df()
    except Exception as e:
        con.close()
        return {"error": f"No se encontró una declaración para el intento {intento}. Primero declara el VaR semanal."}
    con.close()

    if decl.empty:
        return {"error": f"No hay declaración registrada para el intento {intento}."}

    row              = decl.iloc[0]
    var_semanal_usd  = float(row["var_semanal_usd"])
    var_semanal_pct  = float(row["var_semanal_pct"])   # negativo
    fecha_inicio_str = str(row["fecha_inicio"])
    fecha_fin_str    = str(row["fecha_fin"])
    valor_portafolio = float(row["valor_portafolio"])
    nivel_confianza  = float(row["nivel_confianza"])

    fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")
    fecha_fin    = datetime.strptime(fecha_fin_str,    "%Y-%m-%d")

    # ── Descargar precios de la semana real ───────────────────────────────────
    tickers = ["F", "UEC"]
    pesos   = {"F": 0.30, "UEC": 0.70}

    hoy = datetime.today()
    # Descargar hasta hoy o hasta viernes, lo que sea menor
    fecha_descarga_fin = min(hoy + timedelta(days=1), fecha_fin + timedelta(days=1))
    # Incluir día previo al lunes para poder calcular el primer retorno
    fecha_descarga_ini = fecha_inicio - timedelta(days=3)  # incluye viernes previo

    try:
        raw = yf.download(
            tickers,
            start=fecha_descarga_ini.strftime("%Y-%m-%d"),
            end=fecha_descarga_fin.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=True,
            group_by="ticker",
        )
    except Exception as e:
        return {"error": f"No se pudieron descargar precios de la semana: {e}"}

    if raw.empty:
        return {
            "estado":              "EN_CURSO",
            "dias_monitoreados":   0,
            "violaciones":         0,
            "var_semanal_usd":     var_semanal_usd,
            "fecha_inicio":        fecha_inicio_str,
            "fecha_fin":           fecha_fin_str,
            "retornos_acumulados": [],
            "fechas_reales":       [],
        }

    # ── Construir serie de retornos diarios del portafolio ────────────────────
    dfs = {}
    for ticker in tickers:
        try:
            df_t = raw[["Close"]].copy() if len(tickers) == 1 else raw[ticker][["Close"]].copy()
            df_t.columns = ["close"]
            df_t = df_t.dropna().reset_index()
            df_t.rename(columns={"Date": "fecha"}, inplace=True)
            df_t["fecha"] = pd.to_datetime(df_t["fecha"])
            dfs[ticker] = df_t.set_index("fecha")["close"]
        except Exception:
            pass

    if len(dfs) == 0:
        return {"error": "No se pudieron procesar los precios descargados."}

    precios = pd.DataFrame(dfs).sort_index()
    retornos_ind = np.log(precios / precios.shift(1)).dropna()

    # Filtrar solo días de la semana declarada
    retornos_semana = retornos_ind[
        (retornos_ind.index >= fecha_inicio) &
        (retornos_ind.index <= fecha_fin)
    ]

    if retornos_semana.empty:
        return {
            "estado":              "EN_CURSO",
            "dias_monitoreados":   0,
            "violaciones":         0,
            "var_semanal_usd":     var_semanal_usd,
            "fecha_inicio":        fecha_inicio_str,
            "fecha_fin":           fecha_fin_str,
            "retornos_acumulados": [],
            "fechas_reales":       [],
        }

    # ── Calcular retorno acumulado del portafolio ─────────────────────────────
    tickers_ok = [t for t in pesos if t in retornos_semana.columns]
    pesos_arr  = np.array([pesos[t] for t in tickers_ok])
    pesos_arr  = pesos_arr / pesos_arr.sum()

    ret_diario_port = retornos_semana[tickers_ok].values @ pesos_arr
    # Retorno acumulado: suma de retornos log diarios desde el inicio de la semana
    ret_acumulado   = np.cumsum(ret_diario_port)

    # Pérdida acumulada en USD (positivo = pérdida)
    perdida_acum_usd = abs(np.minimum(ret_acumulado, 0)) * valor_portafolio

    fechas_reales    = [d.strftime("%Y-%m-%d") for d in retornos_semana.index]
    dias_monitoreados = len(fechas_reales)

    # ── Verificar violaciones ─────────────────────────────────────────────────
    # Una violación ocurre cuando la PÉRDIDA acumulada supera el VaR semanal declarado
    violaciones = int(np.sum(perdida_acum_usd > var_semanal_usd))

    # Estado
    semana_completa = hoy.date() > fecha_fin.date()
    if violaciones > 0:
        estado = "VIOLADO"
    elif semana_completa:
        estado = "RESPETADO"
    else:
        estado = "EN_CURSO"

    # ── Actualizar estado en BD ───────────────────────────────────────────────
    con = get_connection()
    try:
        con.execute(
            f"UPDATE gold.declaraciones_semanales SET estado = '{estado}' WHERE intento = {intento}"
        )
    except Exception:
        pass
    con.close()

    print(f"[MONITOR] Intento {intento} | Estado: {estado} | Días: {dias_monitoreados}/5 | Violaciones: {violaciones}")

    return {
        "estado":              estado,
        "dias_monitoreados":   dias_monitoreados,
        "violaciones":         violaciones,
        "var_semanal_usd":     var_semanal_usd,
        "var_semanal_pct":     var_semanal_pct,
        "valor_portafolio":    valor_portafolio,
        "nivel_confianza":     nivel_confianza,
        "fecha_inicio":        fecha_inicio_str,
        "fecha_fin":           fecha_fin_str,
        "retornos_acumulados": ret_acumulado.tolist(),
        "perdidas_acum_usd":   perdida_acum_usd.tolist(),
        "fechas_reales":       fechas_reales,
        "intento":             intento,
    }
