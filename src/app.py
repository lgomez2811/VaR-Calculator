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


def calcular_var(
    tickers_texto: str,
    pesos_texto: str,
    nivel_confianza: float,
    valor_portafolio: float,
    periodo_dias: int,
):
    try:
        tickers = [t.strip().upper() for t in tickers_texto.split(",") if t.strip()]
        pesos_raw = [float(p.strip()) for p in pesos_texto.split(",") if p.strip()]
    except ValueError:
        error_msg = "❌ Verifica que los tickers y pesos estén separados por comas y los pesos sean números."
        return error_msg, None, None, None, None, None

    if len(tickers) == 0:
        return "❌ Por favor ingresa al menos un ticker (ej: AAPL, MSFT)", None, None, None, None, None

    if len(tickers) != len(pesos_raw):
        return (
            f"❌ Tienes {len(tickers)} tickers pero {len(pesos_raw)} pesos. Deben ser iguales.",
            None, None, None, None, None
        )

    total_pesos = sum(pesos_raw)
    pesos_norm = [p / total_pesos for p in pesos_raw]
    pesos_dict = dict(zip(tickers, pesos_norm))

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

    var_pct    = resultado["var_pct"]
    var_dinero = resultado["var_dinero"]
    cvar_pct   = resultado["cvar_pct"]
    cvar_dinero = resultado["cvar_dinero"]
    n_obs      = resultado["num_observaciones"]
    pesos_finales = resultado["pesos"]

    composicion = "\n".join([
        f"  · **{t}** — {p:.1%}" for t, p in pesos_finales.items()
    ])

    signo = "$"

    # ── Resumen con métricas destacadas ─────────────────────────────────────
    resumen = f"""
## ✅ Cálculo completado

---

### Portafolio analizado
{composicion}

**Valor:** {signo}{valor_portafolio:,.0f} USD &nbsp;|&nbsp; **Período:** {periodo_dias} días ({n_obs} observaciones) &nbsp;|&nbsp; **Confianza:** {nivel_confianza:.0f}%

---

<div class="metrics-highlight">
  <div class="metric-card var-card">
    <div class="metric-label">VaR ({nivel_confianza:.0f}%)</div>
    <div class="metric-value-pct">{abs(var_pct):.3%}</div>
    <div class="metric-value-usd">{signo}{var_dinero:,.2f} USD</div>
    <div class="metric-desc">Pérdida máxima en 1 día con {nivel_confianza:.0f}% de confianza</div>
  </div>
  <div class="metric-card cvar-card">
    <div class="metric-label">CVaR — Expected Shortfall</div>
    <div class="metric-value-pct">{abs(cvar_pct):.3%}</div>
    <div class="metric-value-usd">{signo}{cvar_dinero:,.2f} USD</div>
    <div class="metric-desc">Pérdida promedio en el {100 - nivel_confianza:.0f}% de peores escenarios</div>
  </div>
</div>

---

### Interpretación

Con confianza del **{nivel_confianza:.0f}%**, hay un **{100 - nivel_confianza:.0f}%** de probabilidad de perder más de **{signo}{var_dinero:,.2f} USD** en un solo día de mercado.

En los peores escenarios (el {100 - nivel_confianza:.0f}% más adverso), la pérdida promedio esperada (**CVaR**) es de **{signo}{cvar_dinero:,.2f} USD**.
"""

    fig_dist    = grafico_distribucion_retornos(resultado)
    fig_precios = grafico_precios_historicos(resultado)
    fig_retornos = grafico_retornos_tiempo(resultado)
    fig_comp    = grafico_composicion(pesos_finales)
    fig_corr    = grafico_correlacion(resultado)

    return resumen, fig_dist, fig_precios, fig_retornos, fig_comp, fig_corr


# ─── CSS personalizado ────────────────────────────────────────────────────────
CSS = """
/* ── Fuentes ── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

/* ── Variables de color ── */
:root {
    --bg-base:       #08101F;
    --bg-surface:    #0F1A2E;
    --bg-card:       #14243D;
    --bg-input:      #1A2E4A;
    --accent-teal:   #00D4AA;
    --accent-orange: #F97316;
    --accent-blue:   #3B82F6;
    --text-primary:  #E2E8F0;
    --text-secondary:#94A3B8;
    --text-muted:    #475569;
    --border-color:  rgba(0, 212, 170, 0.15);
    --border-hover:  rgba(0, 212, 170, 0.35);
    --glow-teal:     0 0 20px rgba(0, 212, 170, 0.08);
}

/* ── Base ── */
.gradio-container, body, .wrap {
    background: var(--bg-base) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    color: var(--text-primary) !important;
}

/* ── Header ── */
.header-container {
    background: linear-gradient(135deg, var(--bg-surface) 0%, #0A1628 100%);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 2rem 2.5rem;
    margin-bottom: 1.5rem;
    position: relative;
    overflow: hidden;
}

.header-container::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, var(--accent-teal), transparent);
}

.header-ticker {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    color: var(--accent-teal);
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
    opacity: 0.8;
}

.header-title {
    font-size: 1.75rem !important;
    font-weight: 600 !important;
    color: var(--text-primary) !important;
    margin: 0 !important;
    letter-spacing: -0.02em;
}

.header-subtitle {
    color: var(--text-secondary) !important;
    font-size: 0.875rem !important;
    margin-top: 0.25rem !important;
    font-weight: 300;
}

/* ── Bloques / panels ── */
.block, .panel, .form {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 10px !important;
}

/* ── Labels ── */
label, .label-wrap span, .svelte-1gfkn6j {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
}

/* ── Inputs ── */
input[type="text"], input[type="number"], textarea, select {
    background: var(--bg-input) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
    border-radius: 8px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
    transition: border-color 0.2s ease !important;
}

input[type="text"]:focus, input[type="number"]:focus, textarea:focus {
    border-color: var(--accent-teal) !important;
    outline: none !important;
    box-shadow: 0 0 0 3px rgba(0, 212, 170, 0.08) !important;
}

/* ── Dropdown ── */
.dropdown, select {
    background: var(--bg-input) !important;
    border-color: var(--border-color) !important;
    color: var(--text-primary) !important;
}

/* ── Slider ── */
input[type="range"] {
    accent-color: var(--accent-teal) !important;
}

/* ── Botón principal ── */
.btn-primary, button.primary, #calcular-btn {
    background: var(--accent-teal) !important;
    color: #08101F !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 0.75rem 2rem !important;
    cursor: pointer !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 20px rgba(0, 212, 170, 0.25) !important;
}

.btn-primary:hover, button.primary:hover {
    background: #00EDBC !important;
    box-shadow: 0 6px 28px rgba(0, 212, 170, 0.4) !important;
    transform: translateY(-1px) !important;
}

/* ── Markdown outputs ── */
.prose, .md-output, .markdown-body {
    background: transparent !important;
    color: var(--text-primary) !important;
}

.prose h2, .prose h3 {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    border-bottom: 1px solid var(--border-color) !important;
    padding-bottom: 0.5rem !important;
}

.prose table {
    border-collapse: collapse !important;
    width: 100% !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
}

.prose table th {
    background: var(--bg-card) !important;
    color: var(--accent-teal) !important;
    font-size: 11px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    padding: 0.6rem 1rem !important;
    border: 1px solid var(--border-color) !important;
}

.prose table td {
    padding: 0.6rem 1rem !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
}

.prose table tr:nth-child(even) td {
    background: rgba(0, 212, 170, 0.03) !important;
}

/* ── Plotly plots ── */
.plot-container, .js-plotly-plot {
    background: transparent !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 10px !important;
}

/* ── Divisor ── */
hr {
    border: none !important;
    border-top: 1px solid var(--border-color) !important;
    margin: 1.5rem 0 !important;
}

/* ── Info text ── */
.info-text, .description {
    color: var(--text-muted) !important;
    font-size: 11px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

/* ── Tabs ── */
.tab-nav, .tabs {
    border-bottom: 1px solid var(--border-color) !important;
    background: transparent !important;
}

.tab-nav button {
    color: var(--text-secondary) !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    border: none !important;
    background: transparent !important;
    padding: 0.75rem 1.25rem !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.2s !important;
}

.tab-nav button.selected {
    color: var(--accent-teal) !important;
    border-bottom-color: var(--accent-teal) !important;
}

/* ── Accordion ── */
.accordion {
    border: 1px solid var(--border-color) !important;
    border-radius: 8px !important;
    background: var(--bg-card) !important;
}

/* ── Footer ── */
.footer-bar {
    border-top: 1px solid var(--border-color);
    padding: 1rem 0;
    margin-top: 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

/* ── Scroll ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--bg-card); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ── CARDS DE MÉTRICAS DESTACADAS ── */
.metrics-highlight {
    display: flex;
    gap: 1.25rem;
    margin: 1.25rem 0;
    flex-wrap: wrap;
}

.metric-card {
    flex: 1;
    min-width: 220px;
    border-radius: 12px;
    padding: 1.5rem 1.75rem;
    position: relative;
    overflow: hidden;
}

.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
}

.var-card {
    background: linear-gradient(135deg, rgba(0,212,170,0.08) 0%, rgba(0,212,170,0.03) 100%);
    border: 1px solid rgba(0,212,170,0.3);
}

.var-card::before {
    background: linear-gradient(90deg, transparent, #00D4AA, transparent);
}

.cvar-card {
    background: linear-gradient(135deg, rgba(249,115,22,0.08) 0%, rgba(249,115,22,0.03) 100%);
    border: 1px solid rgba(249,115,22,0.3);
}

.cvar-card::before {
    background: linear-gradient(90deg, transparent, #F97316, transparent);
}

.metric-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.5rem;
}

.metric-value-pct {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2.75rem;
    font-weight: 600;
    line-height: 1;
    margin-bottom: 0.35rem;
    letter-spacing: -0.02em;
}

.var-card .metric-value-pct {
    color: #00D4AA;
}

.cvar-card .metric-value-pct {
    color: #F97316;
}

.metric-value-usd {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.35rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: 0.75rem;
}

.metric-desc {
    font-size: 12px;
    color: var(--text-muted);
    font-family: 'IBM Plex Sans', sans-serif;
    line-height: 1.4;
}

/* ── Código en metodología ── */
.prose code, .prose pre, code, pre {
    background: var(--bg-card) !important;
    color: var(--accent-teal) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: 6px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 13px !important;
}

.prose pre code, pre code {
    background: transparent !important;
    border: none !important;
    color: var(--accent-teal) !important;
}
"""

# ─── Tema base ────────────────────────────────────────────────────────────────
tema = gr.themes.Base(
    primary_hue=gr.themes.colors.emerald,
    secondary_hue=gr.themes.colors.slate,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("IBM Plex Sans"), "sans-serif"],
    font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "monospace"],
).set(
    body_background_fill="#08101F",
    body_background_fill_dark="#08101F",
    body_text_color="#E2E8F0",
    body_text_color_dark="#E2E8F0",
    block_background_fill="#0F1A2E",
    block_background_fill_dark="#0F1A2E",
    block_border_color="rgba(0,212,170,0.15)",
    block_border_color_dark="rgba(0,212,170,0.15)",
    block_label_text_color="#94A3B8",
    block_label_text_color_dark="#94A3B8",
    input_background_fill="#1A2E4A",
    input_background_fill_dark="#1A2E4A",
    input_border_color="rgba(0,212,170,0.2)",
    input_border_color_dark="rgba(0,212,170,0.2)",
    input_border_color_focus="rgba(0,212,170,0.7)",
    input_border_color_focus_dark="rgba(0,212,170,0.7)",
    input_placeholder_color="#475569",
    input_placeholder_color_dark="#475569",
    slider_color="#00D4AA",
    slider_color_dark="#00D4AA",
    button_primary_background_fill="#00D4AA",
    button_primary_background_fill_dark="#00D4AA",
    button_primary_background_fill_hover="#00EDBC",
    button_primary_background_fill_hover_dark="#00EDBC",
    button_primary_text_color="#08101F",
    button_primary_text_color_dark="#08101F",
    button_secondary_background_fill="#14243D",
    button_secondary_background_fill_dark="#14243D",
    button_secondary_text_color="#E2E8F0",
    button_secondary_text_color_dark="#E2E8F0",
    button_secondary_border_color="rgba(0,212,170,0.2)",
    button_secondary_border_color_dark="rgba(0,212,170,0.2)",
    table_even_background_fill="#14243D",
    table_even_background_fill_dark="#14243D",
    table_odd_background_fill="#0F1A2E",
    table_odd_background_fill_dark="#0F1A2E",
)


# ─── Interfaz Gradio ──────────────────────────────────────────────────────────
with gr.Blocks(
    title="VaR Terminal — Risk Analytics",
) as demo:

    # ── Header — sin pipeline status ni "Medallion" ─────────────────────────
    gr.HTML("""
    <div class="header-container">
        <div class="header-ticker">▸ VAR TERMINAL &nbsp;·&nbsp; RISK ANALYTICS SYSTEM &nbsp;·&nbsp; HISTORICAL SIMULATION</div>
        <h1 class="header-title">Value at Risk Calculator</h1>
        <p class="header-subtitle">
            Simulación histórica · Datos: Yahoo Finance
        </p>
    </div>
    """)

    # ── Tabs principales ──────────────────────────────────────────────────
    tabs = gr.Tabs(selected="config")

    with tabs:

        # ── TAB 1: Configuración ─────────────────────────────────────────
        with gr.TabItem("⚙  Configuración del Portafolio", id="config"):

            # Inputs principales
            with gr.Row(equal_height=True):
                with gr.Column(scale=3):
                    gr.HTML('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#94A3B8;margin-bottom:.5rem;">Composición del portafolio</p>')
                    tickers_input = gr.Textbox(
                        label="Tickers (separados por comas)",
                        placeholder="AAPL, MSFT, GOOGL, AMZN, NVDA",
                        value="AAPL, MSFT, GOOGL",
                        info="Símbolos de Yahoo Finance. Ej: AAPL · MSFT · TSLA · BTC-USD",
                        lines=1,
                    )
                    pesos_input = gr.Textbox(
                        label="Pesos del portafolio (separados por comas)",
                        placeholder="0.40, 0.35, 0.25",
                        value="0.4, 0.35, 0.25",
                        info="Se normalizan automáticamente. Puedes usar 40, 35, 25 o 0.4, 0.35, 0.25",
                        lines=1,
                    )

                with gr.Column(scale=2):
                    gr.HTML('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#94A3B8;margin-bottom:.5rem;">Parámetros de riesgo</p>')
                    confianza_slider = gr.Slider(
                        minimum=90,
                        maximum=99,
                        value=95,
                        step=1,
                        label="Nivel de confianza (%)",
                        info="95% es el estándar de la industria (Basel III)",
                    )
                    valor_input = gr.Number(
                        label="Valor del portafolio (USD)",
                        value=100_000,
                        minimum=1_000,
                        info="Capital total invertido en dólares",
                    )
                    # CAMBIO 3: Período ampliado a 5 años (1825 días)
                    periodo_slider = gr.Slider(
                        minimum=90,
                        maximum=1825,
                        value=365,
                        step=30,
                        label="Período histórico (días)",
                        info="252 días = 1 año bursátil · 365 = 1 año · 730 = 2 años · 1825 = 5 años",
                    )

            gr.HTML('<div style="height:1.25rem;"></div>')

            calcular_btn = gr.Button(
                "▶  Ejecutar Pipeline & Calcular VaR",
                variant="primary",
                size="lg",
                elem_id="calcular-btn",
            )

        # ── TAB 2: Resultados ────────────────────────────────────────────
        with gr.TabItem("📊  Resultados & Análisis", id="resultados"):

            resumen_output = gr.Markdown(
                value="> *Ejecuta el pipeline desde la pestaña de Configuración para ver los resultados aquí.*",
                label="",
            )

            gr.HTML('<div style="height:1rem;"></div>')

            # Fila 1: distribución + composición
            with gr.Row():
                with gr.Column(scale=3):
                    fig_dist_output = gr.Plot(label="Distribución de Retornos & VaR", show_label=True)
                with gr.Column(scale=2):
                    fig_comp_output = gr.Plot(label="Composición del Portafolio", show_label=True)

            # Fila 2: precios históricos
            with gr.Row():
                fig_precios_output = gr.Plot(label="Evolución de Precios (Base 100)", show_label=True)

            # Fila 3: retornos + correlación
            with gr.Row():
                with gr.Column(scale=3):
                    fig_retornos_output = gr.Plot(label="Retornos Diarios del Portafolio", show_label=True)
                with gr.Column(scale=2):
                    fig_corr_output = gr.Plot(label="Mapa de Correlación", show_label=True)

        # ── TAB 3: Documentación ─────────────────────────────────────────
        with gr.TabItem("📖  Metodología", id="metodologia"):
            gr.Markdown("""
## Value at Risk — Metodología

### ¿Qué es el VaR histórico?
El **VaR (Value at Risk)** histórico estima la pérdida máxima esperada de un portafolio durante un período dado, a un nivel de confianza determinado, usando la distribución empírica de retornos pasados.

### Pipeline de datos

| Capa | Herramienta | Proceso |
|------|------------|---------|
| **Bronze** | yfinance + DuckDB | Descarga precios crudos de Yahoo Finance |
| **Silver** | pandas + DuckDB | Limpieza y cálculo de retornos logarítmicos |
| **Gold** | numpy + DuckDB | Cálculo de VaR histórico y CVaR del portafolio |

### Fórmulas clave

**Retorno logarítmico diario:**
```
r_t = ln(P_t / P_{t-1})
```

**Retorno del portafolio:**
```
r_portfolio = Σ (w_i · r_i)
```

**VaR histórico al nivel α:**
```
VaR_α = Percentil(1-α) de {r_portfolio}
```

**CVaR (Expected Shortfall):**
```
CVaR_α = E[r | r ≤ VaR_α]
```

### Interpretación del CVaR
El CVaR (también llamado *Expected Shortfall*) es una métrica más conservadora que el VaR: mide la **pérdida promedio en los peores escenarios**, lo que lo hace preferido en marcos regulatorios modernos (FRTB/Basel IV).

---
> ⚠️ *Proyecto académico. El VaR histórico asume que el pasado es representativo del futuro, lo cual no siempre se cumple en condiciones de estrés de mercado.*
            """)

    # ── Footer ────────────────────────────────────────────────────────────
    gr.HTML("""
    <div style="border-top:1px solid rgba(0,212,170,0.15); margin-top:2rem; padding-top:1rem; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:.5rem;">
        <div style="display:flex;gap:.5rem;flex-wrap:wrap;">
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;letter-spacing:.06em;">yfinance</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;letter-spacing:.06em;">DuckDB</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;letter-spacing:.06em;">Prefect</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;letter-spacing:.06em;">Plotly</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;letter-spacing:.06em;">Gradio</span>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#475569;">⚠ Fines académicos · El VaR histórico no garantiza resultados futuros</span>
    </div>
    """)

    # ── Eventos ───────────────────────────────────────────────────────────
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
    ).then(
        fn=lambda: gr.Tabs(selected="resultados"),
        inputs=None,
        outputs=[tabs],
    )


if __name__ == "__main__":
    demo.launch(
        share=False,
        show_error=True,
        server_port=7860,
        theme=tema,
        css=CSS,
    )
