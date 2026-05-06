"""
app.py
------
Interfaz gráfica interactiva con Gradio para calcular el VaR de un portafolio.

Para ejecutar:
    python src/app.py

La app abre en tu navegador en: http://localhost:7860
"""

import gradio as gr
import pandas as pd
import numpy as np
from pipeline import ejecutar_pipeline_completo
from graficos import (
    grafico_distribucion_retornos,
    grafico_precios_historicos,
    grafico_retornos_tiempo,
    grafico_composicion,
    grafico_correlacion,
)

# ─── Portafolios de ejemplo ───────────────────────────────────────────────────
PORTAFOLIOS_EJEMPLO = {
    "Warren Buffett (estilo Berkshire)": {
        "tickers": "AAPL, BAC, KO, AXP, CVX",
        "pesos": "0.40, 0.20, 0.15, 0.15, 0.10",
        "valor": 1_000_000,
    },
    "Tech Growth (Cathie Wood estilo ARK)": {
        "tickers": "TSLA, NVDA, META, AMZN, GOOGL",
        "pesos": "0.25, 0.25, 0.20, 0.15, 0.15",
        "valor": 500_000,
    },
    "Portafolio Conservador (Bonos + Blue chips)": {
        "tickers": "JNJ, PG, WMT, VZ, T",
        "pesos": "0.25, 0.25, 0.20, 0.15, 0.15",
        "valor": 250_000,
    },
    "S&P 500 Top 5": {
        "tickers": "AAPL, MSFT, NVDA, AMZN, META",
        "pesos": "0.25, 0.25, 0.20, 0.15, 0.15",
        "valor": 100_000,
    },
}


def cargar_ejemplo(nombre_ejemplo):
    """Rellena los campos con el portafolio de ejemplo seleccionado."""
    if nombre_ejemplo == "-- Selecciona un ejemplo --":
        return gr.update(), gr.update(), gr.update()
    ejemplo = PORTAFOLIOS_EJEMPLO[nombre_ejemplo]
    return ejemplo["tickers"], ejemplo["pesos"], ejemplo["valor"]


def calcular_var(
    tickers_texto: str,
    pesos_texto: str,
    nivel_confianza: float,
    valor_portafolio: float,
    periodo_dias: int,
):
    """
    Función principal que conecta la interfaz con el pipeline de datos.
    Retorna todos los gráficos y el resumen de resultados.
    """
    # Validar entradas
    try:
        tickers = [t.strip().upper() for t in tickers_texto.split(",") if t.strip()]
        pesos_raw = [float(p.strip()) for p in pesos_texto.split(",") if p.strip()]
    except ValueError:
        error_msg = "❌ Error: Verifica que los tickers y pesos estén separados por comas y los pesos sean números."
        return error_msg, None, None, None, None, None

    if len(tickers) == 0:
        return "❌ Por favor ingresa al menos un ticker (ej: AAPL, MSFT)", None, None, None, None, None

    if len(tickers) != len(pesos_raw):
        return (
            f"❌ Tienes {len(tickers)} tickers pero {len(pesos_raw)} pesos. Deben ser iguales.",
            None, None, None, None, None
        )

    # Normalizar pesos
    total_pesos = sum(pesos_raw)
    pesos_norm = [p / total_pesos for p in pesos_raw]
    pesos_dict = dict(zip(tickers, pesos_norm))

    # Correr el pipeline completo
    try:
        resultado = ejecutar_pipeline_completo(
            tickers=tickers,
            pesos=pesos_dict,
            nivel_confianza=nivel_confianza / 100,
            valor_portafolio=valor_portafolio,
            periodo_dias=int(periodo_dias),
        )
    except Exception as e:
        return f"❌ Error al correr el pipeline: {str(e)}", None, None, None, None, None

    if "error" in resultado:
        return f"❌ {resultado['error']}", None, None, None, None, None

    # Construir resumen de texto
    var_pct = resultado["var_pct"]
    var_dinero = resultado["var_dinero"]
    cvar_pct = resultado["cvar_pct"]
    cvar_dinero = resultado["cvar_dinero"]
    n_obs = resultado["num_observaciones"]
    pesos_finales = resultado["pesos"]

    composicion = "\n".join([
        f"  • {t}: {p:.1%}" for t, p in pesos_finales.items()
    ])

    resumen = f"""
✅ **Cálculo completado exitosamente**

---
### 📋 Portafolio analizado
{composicion}

**Valor del portafolio:** ${valor_portafolio:,.0f} USD  
**Período analizado:** {periodo_dias} días ({n_obs} observaciones de retornos)  
**Nivel de confianza:** {nivel_confianza:.0f}%

---
### 📊 Resultados de Riesgo

| Métrica | En % | En Dólares |
|---------|------|-----------|
| **VaR ({nivel_confianza:.0f}%)** | {abs(var_pct):.2%} | ${var_dinero:,.2f} |
| **CVaR (Expected Shortfall)** | {abs(cvar_pct):.2%} | ${cvar_dinero:,.2f} |

---
### 💡 ¿Qué significa esto?

Con un nivel de confianza del **{nivel_confianza:.0f}%**, existe un **{100 - nivel_confianza:.0f}%** de probabilidad de que el portafolio pierda **más de ${var_dinero:,.2f} USD** en un solo día de mercado.

El **CVaR** indica que, en los peores escenarios (el {100 - nivel_confianza:.0f}% más malo), la pérdida promedio esperada es de **${cvar_dinero:,.2f} USD**.
"""

    # Generar gráficos
    fig_dist = grafico_distribucion_retornos(resultado)
    fig_precios = grafico_precios_historicos(resultado)
    fig_retornos = grafico_retornos_tiempo(resultado)
    fig_comp = grafico_composicion(pesos_finales)
    fig_corr = grafico_correlacion(resultado)

    return resumen, fig_dist, fig_precios, fig_retornos, fig_comp, fig_corr


# ─── Interfaz Gradio ──────────────────────────────────────────────────────────
with gr.Blocks(
    title="VaR Calculator — Sistema de Riesgo de Portafolio",
    theme=gr.themes.Soft(primary_hue="blue"),
) as demo:

    gr.Markdown("""
    # 📈 Sistema de Cálculo de Value at Risk (VaR)
    ### Simulación Histórica para Portafolios de Activos Financieros
    > Ingresa los tickers de tus acciones, sus pesos y el valor del portafolio. El sistema descarga los datos históricos de Yahoo Finance y calcula el riesgo automáticamente.
    """)

    # ── Fila de ejemplos
    with gr.Row():
        ejemplo_dropdown = gr.Dropdown(
            choices=["-- Selecciona un ejemplo --"] + list(PORTAFOLIOS_EJEMPLO.keys()),
            value="-- Selecciona un ejemplo --",
            label="🎯 Cargar portafolio de ejemplo (opcional)",
            scale=3
        )

    gr.Markdown("---")

    # ── Entradas
    with gr.Row():
        with gr.Column(scale=2):
            tickers_input = gr.Textbox(
                label="📌 Tickers (separados por comas)",
                placeholder="Ej: AAPL, MSFT, GOOGL, AMZN",
                value="AAPL, MSFT, GOOGL",
                info="Usa los símbolos de Yahoo Finance. Ej: AAPL para Apple, MSFT para Microsoft"
            )
            pesos_input = gr.Textbox(
                label="⚖️ Pesos del portafolio (separados por comas)",
                placeholder="Ej: 0.4, 0.35, 0.25",
                value="0.4, 0.35, 0.25",
                info="Los pesos se normalizan automáticamente. Puedes usar 40, 35, 25 o 0.4, 0.35, 0.25"
            )

        with gr.Column(scale=1):
            confianza_slider = gr.Slider(
                minimum=90,
                maximum=99,
                value=95,
                step=1,
                label="🎯 Nivel de Confianza (%)",
                info="95% es el estándar de la industria"
            )
            valor_input = gr.Number(
                label="💵 Valor del Portafolio (USD)",
                value=100_000,
                minimum=1000,
                info="Valor total invertido en dólares"
            )
            periodo_slider = gr.Slider(
                minimum=90,
                maximum=730,
                value=365,
                step=30,
                label="📅 Período histórico (días)",
                info="252 días = 1 año hábil. Más días = más datos"
            )

    calcular_btn = gr.Button(
        "⚡ Calcular VaR",
        variant="primary",
        size="lg"
    )

    gr.Markdown("---")

    # ── Resultados
    resumen_output = gr.Markdown(label="Resultados")

    with gr.Row():
        fig_dist_output = gr.Plot(label="Distribución de Retornos")
        fig_comp_output = gr.Plot(label="Composición del Portafolio")

    with gr.Row():
        fig_precios_output = gr.Plot(label="Evolución de Precios")

    with gr.Row():
        fig_retornos_output = gr.Plot(label="Retornos en el Tiempo")
        fig_corr_output = gr.Plot(label="Correlación entre Activos")

    # ── Footer
    gr.Markdown("""
    ---
    > 📚 **Metodología:** Simulación histórica · **Datos:** Yahoo Finance (yfinance) · **Arquitectura:** Bronze → Silver → Gold (Medallion)
    >
    > ⚠️ *Este sistema es para fines académicos. El VaR histórico no garantiza resultados futuros.*
    """)

    # ── Eventos
    ejemplo_dropdown.change(
        fn=cargar_ejemplo,
        inputs=[ejemplo_dropdown],
        outputs=[tickers_input, pesos_input, valor_input]
    )

    calcular_btn.click(
        fn=calcular_var,
        inputs=[tickers_input, pesos_input, confianza_slider, valor_input, periodo_slider],
        outputs=[
            resumen_output,
            fig_dist_output,
            fig_precios_output,
            fig_retornos_output,
            fig_comp_output,
            fig_corr_output,
        ],
    )


if __name__ == "__main__":
    demo.launch(
        share=False,      # Cambia a True si quieres un link público temporal
        show_error=True,
        server_port=7860,
    )
