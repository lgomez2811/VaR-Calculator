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
from datetime import datetime, timedelta
from pipeline import ejecutar_pipeline_completo, declarar_var_semanal, monitorear_var_semanal
from graficos import (
    grafico_distribucion_retornos,
    grafico_precios_historicos,
    grafico_retornos_tiempo,
    grafico_composicion,
    grafico_correlacion,
    grafico_monitor_semanal,
)

# ─── Portafolio fijo del profesor ────────────────────────────────────────────
PORTAFOLIO_PROFE = {"F": 0.30, "UEC": 0.70}


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
        return "❌ Verifica que los tickers y pesos estén separados por comas.", None, None, None, None, None

    if len(tickers) == 0:
        return "❌ Por favor ingresa al menos un ticker (ej: AAPL, MSFT)", None, None, None, None, None
    if len(tickers) != len(pesos_raw):
        return (f"❌ Tienes {len(tickers)} tickers pero {len(pesos_raw)} pesos.", None, None, None, None, None)

    total_pesos = sum(pesos_raw)
    if abs(total_pesos - 1.0) > 0.001 and abs(total_pesos - 100.0) > 0.1:
        return (
            f"❌ Los pesos suman **{total_pesos:.4f}** ({total_pesos * 100:.2f}% si usas escala 0→1). "
            f"Deben sumar **1.0** (ej: 0.30, 0.70) o **100** (ej: 30, 70). "
            f"Por favor ajusta los valores antes de continuar.",
            None, None, None, None, None
        )
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

    var_pct     = resultado["var_pct"]
    var_dinero  = resultado["var_dinero"]
    cvar_pct    = resultado["cvar_pct"]
    cvar_dinero = resultado["cvar_dinero"]
    n_obs       = resultado["num_observaciones"]
    pesos_finales = resultado["pesos"]

    composicion = "\n".join([f"  · **{t}** — {p:.1%}" for t, p in pesos_finales.items()])

    resumen = f"""
## ✅ Cálculo completado

---

### Portafolio analizado
{composicion}

**Valor:** ${valor_portafolio:,.0f} USD &nbsp;|&nbsp; **Período:** {periodo_dias} días ({n_obs} observaciones) &nbsp;|&nbsp; **Confianza:** {nivel_confianza:.0f}%

---

<div class="metrics-highlight">
  <div class="metric-card var-card">
    <div class="metric-label">VaR ({nivel_confianza:.0f}%)</div>
    <div class="metric-value-pct">{abs(var_pct):.3%}</div>
    <div class="metric-value-usd">${var_dinero:,.2f} USD</div>
    <div class="metric-desc">Pérdida máxima en 1 día con {nivel_confianza:.0f}% de confianza</div>
  </div>
  <div class="metric-card cvar-card">
    <div class="metric-label">CVaR — Expected Shortfall</div>
    <div class="metric-value-pct">{abs(cvar_pct):.3%}</div>
    <div class="metric-value-usd">${cvar_dinero:,.2f} USD</div>
    <div class="metric-desc">Pérdida promedio en el {100 - nivel_confianza:.0f}% de peores escenarios</div>
  </div>
</div>

---

### Interpretación

Con confianza del **{nivel_confianza:.0f}%**, hay un **{100 - nivel_confianza:.0f}%** de probabilidad de perder más de **${var_dinero:,.2f} USD** en un solo día de mercado.

En los peores escenarios (el {100 - nivel_confianza:.0f}% más adverso), la pérdida promedio esperada (**CVaR**) es de **${cvar_dinero:,.2f} USD**.
"""

    fig_dist     = grafico_distribucion_retornos(resultado)
    fig_precios  = grafico_precios_historicos(resultado)
    fig_retornos = grafico_retornos_tiempo(resultado)
    fig_comp     = grafico_composicion(pesos_finales)
    fig_corr     = grafico_correlacion(resultado)

    return resumen, fig_dist, fig_precios, fig_retornos, fig_comp, fig_corr


# ─── Funciones del tab semanal ────────────────────────────────────────────────

def calcular_y_declarar_semanal(valor_portafolio: float, nivel_confianza: float, intento: int):
    """Calcula el VaR semanal del portafolio F/UEC y lo guarda como declaración."""
    try:
        resultado = declarar_var_semanal(
            pesos=PORTAFOLIO_PROFE,
            nivel_confianza=nivel_confianza / 100,
            valor_portafolio=valor_portafolio,
            intento=int(intento),
        )
    except Exception as e:
        return f"❌ Error: {str(e)}", None

    if "error" in resultado:
        return f"❌ {resultado['error']}", None

    var_d     = resultado["var_diario_pct"]
    var_s     = resultado["var_semanal_pct"]
    var_usd   = resultado["var_semanal_usd"]
    cvar_s    = resultado["cvar_semanal_pct"]
    cvar_usd  = resultado["cvar_semanal_usd"]
    fecha_ini = resultado["fecha_inicio"]
    fecha_fin = resultado["fecha_fin"]
    n_obs     = resultado["num_observaciones"]

    declaracion = f"""
## 📋 Declaración Oficial — Intento {int(intento)}

---

<div class="metrics-highlight">
  <div class="metric-card var-card">
    <div class="metric-label">VaR Semanal ({nivel_confianza:.0f}%)</div>
    <div class="metric-value-pct">{abs(var_s):.3%}</div>
    <div class="metric-value-usd">${var_usd:,.2f} USD</div>
    <div class="metric-desc">Pérdida máxima esperada en 5 días hábiles</div>
  </div>
  <div class="metric-card cvar-card">
    <div class="metric-label">CVaR Semanal</div>
    <div class="metric-value-pct">{abs(cvar_s):.3%}</div>
    <div class="metric-value-usd">${cvar_usd:,.2f} USD</div>
    <div class="metric-desc">Pérdida promedio en peores escenarios</div>
  </div>
</div>

---

<div class="declaracion-box">
  <div class="decl-header">📌 DECLARACIÓN REGISTRADA EN BASE DE DATOS</div>
  <div class="decl-row"><span class="decl-key">Portafolio</span><span class="decl-val">30% F (Ford) · 70% UEC (Uranium Energy)</span></div>
  <div class="decl-row"><span class="decl-key">Valor declarado</span><span class="decl-val">${valor_portafolio:,.0f} USD</span></div>
  <div class="decl-row"><span class="decl-key">Nivel de confianza</span><span class="decl-val">{nivel_confianza:.0f}%</span></div>
  <div class="decl-row"><span class="decl-key">Fecha de inicio</span><span class="decl-val">{fecha_ini}</span></div>
  <div class="decl-row"><span class="decl-key">Fecha de fin</span><span class="decl-val">{fecha_fin}</span></div>
  <div class="decl-row"><span class="decl-key">VaR diario base</span><span class="decl-val">{abs(var_d):.3%} (escalado × √5)</span></div>
  <div class="decl-row"><span class="decl-key">Observaciones históricas</span><span class="decl-val">{n_obs} días</span></div>
  <div class="decl-row"><span class="decl-key">Intento</span><span class="decl-val">{int(intento)} / 2</span></div>
</div>

---

### ¿Qué significa esto?

Con **{nivel_confianza:.0f}% de confianza**, el portafolio **no debería perder más de ${var_usd:,.2f} USD**
durante la semana del **{fecha_ini}** al **{fecha_fin}**.

Si en **alguno de los 5 días hábiles** la pérdida acumulada desde el inicio de la semana supera ese monto, el VaR se vuela.

> Usa el botón **"Monitorear Semana"** para ver el estado en tiempo real día a día.
"""

    fig = grafico_monitor_semanal(resultado, [])
    return declaracion, fig


def monitorear_semana(intento: int):
    """Descarga precios reales y verifica si el VaR se respetó."""
    try:
        resultado = monitorear_var_semanal(intento=int(intento))
    except Exception as e:
        return f"❌ Error al monitorear: {str(e)}", None

    if "error" in resultado:
        return f"❌ {resultado['error']}", None

    dias            = resultado["dias_monitoreados"]
    violaciones     = resultado["violaciones"]
    estado          = resultado["estado"]   # "EN_CURSO" | "RESPETADO" | "VIOLADO"
    var_usd         = resultado["var_semanal_usd"]
    fecha_ini       = resultado["fecha_inicio"]
    fecha_fin       = resultado["fecha_fin"]
    retornos_reales = resultado.get("retornos_acumulados", [])
    fechas_reales   = resultado.get("fechas_reales", [])

    if estado == "VIOLADO":
        badge      = '<span class="badge badge-red">🔴 VaR VIOLADO — Intento consumido</span>'
        msg_estado = f"La pérdida real superó el VaR declarado (${var_usd:,.2f} USD) en {violaciones} día(s)."
    elif estado == "RESPETADO":
        badge      = '<span class="badge badge-green">🟢 VaR RESPETADO — Ejercicio exitoso</span>'
        msg_estado = f"La semana cerró sin superar el VaR declarado (${var_usd:,.2f} USD). ¡Ejercicio superado!"
    else:
        badge      = '<span class="badge badge-yellow">🟡 EN CURSO — Semana activa</span>'
        msg_estado = f"Faltan {5 - dias} día(s) hábil(es) para completar la semana."

    resumen_monitor = f"""
## 📡 Monitor de Validación — Intento {int(intento)}

{badge}

---

**Semana:** {fecha_ini} → {fecha_fin} &nbsp;|&nbsp; **VaR declarado:** ${var_usd:,.2f} USD &nbsp;|&nbsp; **Días monitoreados:** {dias} / 5

{msg_estado}

{"**⚠ Días con violación:** " + str(violaciones) if violaciones > 0 else "✅ **Sin violaciones registradas.**"}
"""

    decl_base = {"var_semanal_usd": var_usd, "fecha_inicio": fecha_ini, "fecha_fin": fecha_fin}
    fig = grafico_monitor_semanal(
        decl_base, retornos_reales,
        estado=estado, var_usd=var_usd,
        fechas=fechas_reales,
    )

    return resumen_monitor, fig


# ─── CSS ──────────────────────────────────────────────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

:root {
    --bg-base:       #08101F;
    --bg-surface:    #0F1A2E;
    --bg-card:       #14243D;
    --bg-input:      #1A2E4A;
    --accent-teal:   #00D4AA;
    --accent-orange: #F97316;
    --accent-blue:   #3B82F6;
    --accent-red:    #EF4444;
    --accent-green:  #22C55E;
    --text-primary:  #E2E8F0;
    --text-secondary:#94A3B8;
    --text-muted:    #475569;
    --border-color:  rgba(0, 212, 170, 0.15);
}

.gradio-container, body, .wrap {
    background: var(--bg-base) !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
    color: var(--text-primary) !important;
}

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
.header-ticker { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--accent-teal); letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 0.5rem; opacity: 0.8; }
.header-title  { font-size: 1.75rem !important; font-weight: 600 !important; color: var(--text-primary) !important; margin: 0 !important; letter-spacing: -0.02em; }
.header-subtitle { color: var(--text-secondary) !important; font-size: 0.875rem !important; margin-top: 0.25rem !important; font-weight: 300; }

.block, .panel, .form { background: var(--bg-surface) !important; border: 1px solid var(--border-color) !important; border-radius: 10px !important; }

label, .label-wrap span { font-family: 'IBM Plex Mono', monospace !important; font-size: 11px !important; letter-spacing: 0.08em !important; text-transform: uppercase !important; color: var(--text-secondary) !important; font-weight: 500 !important; }

input[type="text"], input[type="number"], textarea, select { background: var(--bg-input) !important; border: 1px solid var(--border-color) !important; color: var(--text-primary) !important; border-radius: 8px !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 13px !important; }
input:focus, textarea:focus { border-color: var(--accent-teal) !important; box-shadow: 0 0 0 3px rgba(0,212,170,0.08) !important; }
input[type="range"] { accent-color: var(--accent-teal) !important; }

button.primary { background: var(--accent-teal) !important; color: #08101F !important; border: none !important; border-radius: 8px !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 13px !important; font-weight: 600 !important; letter-spacing: 0.06em !important; text-transform: uppercase !important; box-shadow: 0 4px 20px rgba(0,212,170,0.25) !important; transition: all 0.2s ease !important; }
button.primary:hover { background: #00EDBC !important; transform: translateY(-1px) !important; }

.prose, .md-output, .markdown-body { background: transparent !important; color: var(--text-primary) !important; }
.prose h2, .prose h3 { color: var(--text-primary) !important; font-weight: 600 !important; border-bottom: 1px solid var(--border-color) !important; padding-bottom: 0.5rem !important; }
.prose table { border-collapse: collapse !important; width: 100% !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 13px !important; }
.prose table th { background: var(--bg-card) !important; color: var(--accent-teal) !important; font-size: 11px !important; text-transform: uppercase !important; padding: 0.6rem 1rem !important; border: 1px solid var(--border-color) !important; }
.prose table td { padding: 0.6rem 1rem !important; border: 1px solid var(--border-color) !important; color: var(--text-primary) !important; }
.prose table tr:nth-child(even) td { background: rgba(0,212,170,0.03) !important; }

.plot-container, .js-plotly-plot { background: transparent !important; border: 1px solid var(--border-color) !important; border-radius: 10px !important; }

hr { border: none !important; border-top: 1px solid var(--border-color) !important; margin: 1.5rem 0 !important; }

.tab-nav button { color: var(--text-secondary) !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 12px !important; letter-spacing: 0.06em !important; text-transform: uppercase !important; border: none !important; background: transparent !important; padding: 0.75rem 1.25rem !important; border-bottom: 2px solid transparent !important; transition: all 0.2s !important; }
.tab-nav button.selected { color: var(--accent-teal) !important; border-bottom-color: var(--accent-teal) !important; }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-base); }
::-webkit-scrollbar-thumb { background: var(--bg-card); border-radius: 3px; }

/* Métricas */
.metrics-highlight { display: flex; gap: 1.25rem; margin: 1.25rem 0; flex-wrap: wrap; }
.metric-card { flex: 1; min-width: 220px; border-radius: 12px; padding: 1.5rem 1.75rem; position: relative; overflow: hidden; }
.metric-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; }
.var-card  { background: linear-gradient(135deg, rgba(0,212,170,0.08), rgba(0,212,170,0.03)); border: 1px solid rgba(0,212,170,0.3); }
.var-card::before  { background: linear-gradient(90deg, transparent, #00D4AA, transparent); }
.cvar-card { background: linear-gradient(135deg, rgba(249,115,22,0.08), rgba(249,115,22,0.03)); border: 1px solid rgba(249,115,22,0.3); }
.cvar-card::before { background: linear-gradient(90deg, transparent, #F97316, transparent); }
.metric-label     { font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 0.5rem; }
.metric-value-pct { font-family: 'IBM Plex Mono', monospace; font-size: 2.75rem; font-weight: 600; line-height: 1; margin-bottom: 0.35rem; letter-spacing: -0.02em; }
.var-card  .metric-value-pct { color: #00D4AA; }
.cvar-card .metric-value-pct { color: #F97316; }
.metric-value-usd { font-family: 'IBM Plex Mono', monospace; font-size: 1.35rem; font-weight: 500; color: var(--text-primary); margin-bottom: 0.75rem; }
.metric-desc { font-size: 12px; color: var(--text-muted); line-height: 1.4; }

/* Declaración */
.declaracion-box { background: var(--bg-card); border: 1px solid rgba(0,212,170,0.25); border-radius: 10px; padding: 1.25rem 1.5rem; margin: 1rem 0; }
.decl-header { font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent-teal); margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); }
.decl-row { display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0; border-bottom: 1px solid rgba(255,255,255,0.03); }
.decl-key { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.06em; }
.decl-val { font-family: 'IBM Plex Mono', monospace; font-size: 13px; color: var(--text-primary); font-weight: 500; }

/* Badges */
.badge { display: inline-block; padding: 6px 16px; border-radius: 999px; font-family: 'IBM Plex Mono', monospace; font-size: 12px; font-weight: 600; letter-spacing: 0.06em; }
.badge-green  { background: rgba(34,197,94,0.15);  border: 1px solid rgba(34,197,94,0.4);  color: #22C55E; }
.badge-red    { background: rgba(239,68,68,0.15);   border: 1px solid rgba(239,68,68,0.4);  color: #EF4444; }
.badge-yellow { background: rgba(234,179,8,0.15);   border: 1px solid rgba(234,179,8,0.4);  color: #EAB308; }

/* Código metodología */
.prose code, .prose pre, code, pre { background: var(--bg-card) !important; color: var(--accent-teal) !important; border: 1px solid var(--border-color) !important; border-radius: 6px !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 13px !important; }
.prose pre code, pre code { background: transparent !important; border: none !important; }

/* Info semanal */
.info-semanal { background: rgba(0,212,170,0.04); border: 1px solid rgba(0,212,170,0.2); border-radius: 8px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--text-secondary); line-height: 1.8; }
.info-semanal strong { color: var(--accent-teal); }
"""

# ─── Tema ─────────────────────────────────────────────────────────────────────
tema = gr.themes.Base(
    primary_hue=gr.themes.colors.emerald,
    secondary_hue=gr.themes.colors.slate,
    neutral_hue=gr.themes.colors.slate,
    font=[gr.themes.GoogleFont("IBM Plex Sans"), "sans-serif"],
    font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "monospace"],
).set(
    body_background_fill="#08101F", body_background_fill_dark="#08101F",
    body_text_color="#E2E8F0", body_text_color_dark="#E2E8F0",
    block_background_fill="#0F1A2E", block_background_fill_dark="#0F1A2E",
    block_border_color="rgba(0,212,170,0.15)", block_border_color_dark="rgba(0,212,170,0.15)",
    block_label_text_color="#94A3B8", block_label_text_color_dark="#94A3B8",
    input_background_fill="#1A2E4A", input_background_fill_dark="#1A2E4A",
    input_border_color="rgba(0,212,170,0.2)", input_border_color_dark="rgba(0,212,170,0.2)",
    input_border_color_focus="rgba(0,212,170,0.7)", input_border_color_focus_dark="rgba(0,212,170,0.7)",
    input_placeholder_color="#475569", input_placeholder_color_dark="#475569",
    slider_color="#00D4AA", slider_color_dark="#00D4AA",
    button_primary_background_fill="#00D4AA", button_primary_background_fill_dark="#00D4AA",
    button_primary_background_fill_hover="#00EDBC", button_primary_background_fill_hover_dark="#00EDBC",
    button_primary_text_color="#08101F", button_primary_text_color_dark="#08101F",
    button_secondary_background_fill="#14243D", button_secondary_background_fill_dark="#14243D",
    button_secondary_text_color="#E2E8F0", button_secondary_text_color_dark="#E2E8F0",
    button_secondary_border_color="rgba(0,212,170,0.2)", button_secondary_border_color_dark="rgba(0,212,170,0.2)",
    table_even_background_fill="#14243D", table_even_background_fill_dark="#14243D",
    table_odd_background_fill="#0F1A2E", table_odd_background_fill_dark="#0F1A2E",
)


# ─── Interfaz ─────────────────────────────────────────────────────────────────
with gr.Blocks(title="VaR Terminal — Risk Analytics") as demo:

    gr.HTML("""
    <div class="header-container">
        <div class="header-ticker">▸ VAR TERMINAL &nbsp;·&nbsp; RISK ANALYTICS SYSTEM &nbsp;·&nbsp; HISTORICAL SIMULATION</div>
        <h1 class="header-title">Value at Risk Calculator</h1>
        <p class="header-subtitle">Simulación histórica · Datos: Yahoo Finance</p>
    </div>
    """)

    tabs = gr.Tabs(selected="config")

    with tabs:

        # ── TAB 1: Portafolio libre ───────────────────────────────────────
        with gr.TabItem("⚙  Portafolio Libre", id="config"):
            with gr.Row(equal_height=True):
                with gr.Column(scale=3):
                    gr.HTML('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#94A3B8;margin-bottom:.5rem;">Composición del portafolio</p>')
                    tickers_input = gr.Textbox(label="Tickers (separados por comas)", placeholder="AAPL, MSFT, GOOGL", value="AAPL, MSFT, GOOGL", info="Símbolos de Yahoo Finance.")
                    pesos_input   = gr.Textbox(label="Pesos del portafolio (separados por comas)", placeholder="0.40, 0.35, 0.25", value="0.4, 0.35, 0.25", info="Se normalizan automáticamente.")
                with gr.Column(scale=2):
                    gr.HTML('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#94A3B8;margin-bottom:.5rem;">Parámetros de riesgo</p>')
                    confianza_slider = gr.Slider(minimum=90, maximum=99, value=95, step=1,  label="Nivel de confianza (%)", info="95% estándar Basel III")
                    valor_input      = gr.Number(label="Valor del portafolio (USD)", value=100_000, minimum=1_000)
                    periodo_slider   = gr.Slider(minimum=90, maximum=1825, value=365, step=30, label="Período histórico (días)", info="252=1 año · 730=2 años · 1825=5 años")
            gr.HTML('<div style="height:1.25rem;"></div>')
            calcular_btn = gr.Button("▶  Ejecutar Pipeline & Calcular VaR", variant="primary", size="lg", elem_id="calcular-btn")

        # ── TAB 2: Resultados generales ───────────────────────────────────
        with gr.TabItem("📊  Resultados & Análisis", id="resultados"):
            resumen_output = gr.Markdown(value="> *Ejecuta el pipeline desde la pestaña de Configuración.*")
            gr.HTML('<div style="height:1rem;"></div>')
            with gr.Row():
                with gr.Column(scale=3): fig_dist_output     = gr.Plot(label="Distribución de Retornos & VaR", show_label=True)
                with gr.Column(scale=2): fig_comp_output     = gr.Plot(label="Composición del Portafolio", show_label=True)
            with gr.Row():               fig_precios_output  = gr.Plot(label="Evolución de Precios (Base 100)", show_label=True)
            with gr.Row():
                with gr.Column(scale=3): fig_retornos_output = gr.Plot(label="Retornos Diarios del Portafolio", show_label=True)
                with gr.Column(scale=2): fig_corr_output     = gr.Plot(label="Mapa de Correlación", show_label=True)

        # ── TAB 3: VaR Semanal F/UEC ──────────────────────────────────────
        with gr.TabItem("🎯  VaR Semanal — F / UEC", id="semanal"):

            gr.HTML("""
            <div class="info-semanal">
                <strong>PORTAFOLIO FIJO:</strong> 30% F (Ford Motor) · 70% UEC (Uranium Energy Corp)<br>
                <strong>OBJETIVO:</strong> Declarar el VaR semanal y monitorear que no se viole durante 5 días hábiles.<br>
                <strong>REGLA:</strong> Si la pérdida acumulada real supera el VaR en algún día → intento consumido. Tienen 2 intentos.
            </div>
            """)

            with gr.Row(equal_height=True):
                with gr.Column(scale=2):
                    gr.HTML('<p style="font-family:\'IBM Plex Mono\',monospace;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#94A3B8;margin-bottom:.5rem;">Parámetros de la declaración</p>')
                    valor_semanal     = gr.Number(label="Valor del portafolio (USD)", value=100_000, minimum=1_000)
                    confianza_semanal = gr.Slider(minimum=90, maximum=99, value=95, step=1,
                        label="Nivel de confianza (%)",
                        info="A mayor confianza → VaR más alto → más difícil de violar")
                    intento_radio     = gr.Radio(choices=[1, 2], value=1, label="Número de intento")

                with gr.Column(scale=3):
                    gr.HTML("""
                    <div style="background:rgba(0,212,170,0.04);border:1px solid rgba(0,212,170,0.15);border-radius:8px;padding:1.25rem;font-size:12px;color:#94A3B8;font-family:'IBM Plex Mono',monospace;line-height:2;">
                        <b style="color:#00D4AA;">PASO 1 —</b> Ajusta valor y nivel de confianza<br>
                        <b style="color:#00D4AA;">PASO 2 —</b> Presiona <b>"Declarar VaR Semanal"</b><br>
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ Guarda la declaración en DuckDB con fecha inicio y fin<br>
                        <b style="color:#00D4AA;">PASO 3 —</b> Cada día laboral presiona <b>"Monitorear Semana"</b><br>
                        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ Descarga precios reales y verifica si el VaR se violó<br>
                        <b style="color:#F97316;">⚠ IMPORTANTE —</b> Declara solo UNA vez por intento.
                    </div>
                    """)
                    gr.HTML('<div style="height:.75rem;"></div>')
                    declarar_btn    = gr.Button("📋  Declarar VaR Semanal", variant="primary", size="lg")
                    gr.HTML('<div style="height:.5rem;"></div>')
                    monitorear_btn  = gr.Button("📡  Monitorear Semana (actualizar estado)", variant="secondary", size="lg")

            gr.HTML('<div style="height:1rem;"></div>')
            declaracion_output  = gr.Markdown(value="> *Presiona 'Declarar VaR Semanal' para generar la declaración oficial.*")
            fig_monitor_output  = gr.Plot(label="Monitor de VaR Semanal", show_label=True)

        # ── TAB 4: Metodología ────────────────────────────────────────────
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

### Escalado diario → semanal

El VaR semanal se obtiene escalando el VaR diario por la raíz cuadrada del tiempo (estándar Basel II/III):

```
VaR_semanal = VaR_diario × √5
```

Esto asume retornos i.i.d. (independientes e idénticamente distribuidos), válido para horizontes cortos.

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

### Validación semanal

El monitor descarga los precios reales de F y UEC cada día y calcula la pérdida acumulada del portafolio desde el lunes de la semana declarada. Si en algún momento esa pérdida supera el VaR declarado, el intento se considera fallido.

---
> ⚠️ *Proyecto académico. El VaR histórico asume que el pasado es representativo del futuro.*
            """)

    gr.HTML("""
    <div style="border-top:1px solid rgba(0,212,170,0.15);margin-top:2rem;padding-top:1rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem;">
        <div style="display:flex;gap:.5rem;flex-wrap:wrap;">
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;">yfinance</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;">DuckDB</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;">Prefect</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;">Plotly</span>
            <span style="background:#14243D;border:1px solid rgba(0,212,170,0.15);border-radius:999px;padding:3px 12px;font-size:11px;font-family:'IBM Plex Mono',monospace;color:#475569;">Gradio</span>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#475569;">⚠ Fines académicos · No garantiza resultados futuros</span>
    </div>
    """)

    # ── Eventos ───────────────────────────────────────────────────────────
    calcular_btn.click(
        fn=calcular_var,
        inputs=[tickers_input, pesos_input, confianza_slider, valor_input, periodo_slider],
        outputs=[resumen_output, fig_dist_output, fig_precios_output, fig_retornos_output, fig_comp_output, fig_corr_output],
    ).then(fn=lambda: gr.Tabs(selected="resultados"), inputs=None, outputs=[tabs])

    declarar_btn.click(
        fn=calcular_y_declarar_semanal,
        inputs=[valor_semanal, confianza_semanal, intento_radio],
        outputs=[declaracion_output, fig_monitor_output],
    )

    monitorear_btn.click(
        fn=monitorear_semana,
        inputs=[intento_radio],
        outputs=[declaracion_output, fig_monitor_output],
    )


if __name__ == "__main__":
    demo.launch(share=False, show_error=True, server_port=7860, theme=tema, css=CSS)
