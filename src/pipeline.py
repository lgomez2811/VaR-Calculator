"""
pipeline.py
-----------
Pipeline de datos Bronze → Silver → Gold usando:
- Prefect: para orquestar las tareas en orden automático
- DuckDB:  para guardar los datos en capas (bronze, silver, gold)
- yfinance: para descargar precios históricos

Para ver el pipeline corriendo visualmente:
    prefect server start   (en otra terminal)
    Abre: http://localhost:4200
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
# Se guarda en la carpeta data/ del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, "data", "portafolio.duckdb")


def get_connection():
    """
    Abre la base de datos DuckDB y crea los 3 schemas si no existen.
    Siempre llama a esta función para obtener la conexión.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    return con


# ─── TAREA 1: BRONZE ──────────────────────────────────────────────────────────
@task(name="Bronze - Descargar precios", log_prints=True)
def bronze_descargar_precios(tickers: list, periodo_dias: int = 365) -> pd.DataFrame:
    """
    Descarga precios históricos de Yahoo Finance.
    Guarda los datos CRUDOS en DuckDB → bronze.precios
    """
    print(f"[BRONZE] Descargando {tickers} — últimos {periodo_dias} días...")

    fecha_fin    = datetime.today()
    fecha_inicio = fecha_fin - timedelta(days=periodo_dias)

    todos = []

    # Intentar descarga masiva primero (más rápida y menos peticiones)
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
                # Un solo ticker no tiene MultiIndex
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
                datos = yf.download(
                    ticker,
                    start=fecha_inicio.strftime("%Y-%m-%d"),
                    end=fecha_fin.strftime("%Y-%m-%d"),
                    progress=False,
                    auto_adjust=True,
                )
                if datos.empty:
                    print(f"[BRONZE] Sin datos para {ticker}")
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

    # ── Guardar en DuckDB ──
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
    """
    Lee bronze.precios, limpia nulos y calcula retornos logarítmicos.
    Guarda el resultado en DuckDB → silver.precios
    """
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
        print("[SILVER] ⚠ Bronze vacío, nada que procesar.")
        return pd.DataFrame()

    # Limpieza con pandas
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values(["ticker", "fecha"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["close"])

    # Retorno logarítmico: ln(P_hoy / P_ayer)
    df["retorno_log"] = df.groupby("ticker")["close"].transform(
        lambda x: np.log(x / x.shift(1))
    )
    df = df.dropna(subset=["retorno_log"])
    df["procesado_en"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["fecha"]        = df["fecha"].astype(str)

    # ── Guardar en DuckDB ──
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
    """
    Lee silver.precios y calcula el VaR histórico del portafolio.
    Guarda el resumen en DuckDB → gold.resultados
    """
    print(f"[GOLD] Calculando VaR al {nivel_confianza:.0%} para portafolio de ${valor_portafolio:,.0f}...")

    con = get_connection()
    try:
        df = con.table("silver.precios").df()
    except Exception as e:
        con.close()
        return {"error": f"No hay datos en silver.precios: {e}"}
    con.close()

    if df.empty:
        return {"error": "Silver está vacío. Verifica la conexión a internet y los tickers."}

    df["fecha"] = pd.to_datetime(df["fecha"])

    # Pivote: filas=fecha, columnas=ticker, valores=retorno_log
    tabla = df.pivot_table(index="fecha", columns="ticker", values="retorno_log")
    tabla = tabla.dropna()

    tickers_ok = [t for t in pesos if t in tabla.columns]
    if not tickers_ok:
        tickers_en_datos = tabla.columns.tolist()
        return {"error": f"Tickers no encontrados. Los disponibles son: {tickers_en_datos}"}

    tabla = tabla[tickers_ok]

    # Pesos normalizados
    pesos_arr = np.array([pesos[t] for t in tickers_ok])
    pesos_arr = pesos_arr / pesos_arr.sum()

    # Retorno diario del portafolio
    retornos = tabla.values @ pesos_arr

    # VaR histórico
    percentil    = (1 - nivel_confianza) * 100
    var_pct      = np.percentile(retornos, percentil)
    var_dinero   = abs(var_pct) * valor_portafolio

    # CVaR (Expected Shortfall)
    cvar_pct     = retornos[retornos <= var_pct].mean()
    cvar_dinero  = abs(cvar_pct) * valor_portafolio

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

    # Guardar resumen en gold
    resumen = pd.DataFrame([{
        "calculado_en":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tickers":         str(tickers_ok),
        "nivel_confianza": nivel_confianza,
        "var_pct":         round(var_pct,    6),
        "var_dinero":      round(var_dinero,  2),
        "cvar_pct":        round(cvar_pct,   6),
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

    print(f"[GOLD] ✓ VaR={abs(var_pct):.2%}  (${var_dinero:,.2f})  |  CVaR={abs(cvar_pct):.2%}  (${cvar_dinero:,.2f})")
    return resultado


# ─── FLOW PRINCIPAL (Prefect) ─────────────────────────────────────────────────
@flow(name="Pipeline VaR — Bronze→Silver→Gold", log_prints=True)
def ejecutar_pipeline_completo(
    tickers:          list,
    pesos:            dict,
    nivel_confianza:  float,
    valor_portafolio: float,
    periodo_dias:     int = 365,
) -> dict:
    """
    Flow de Prefect que ejecuta las 3 capas en orden:
    Bronze → Silver → Gold

    Prefect garantiza que si una tarea falla, se detiene
    y reporta exactamente cuál falló y por qué.
    """
    bronze_descargar_precios(tickers, periodo_dias)
    silver_limpiar_y_retornos()
    resultado = gold_calcular_var(pesos, nivel_confianza, valor_portafolio)
    return resultado
