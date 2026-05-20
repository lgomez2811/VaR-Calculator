"""
graficos.py
-----------
Funciones para crear gráficos interactivos con Plotly.
Tema oscuro financiero — coherente con VaR Terminal UI.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ─── Paleta de colores del tema ───────────────────────────────────────────────
COLORES = {
    "teal":        "#00D4AA",
    "teal_dim":    "rgba(0, 212, 170, 0.15)",
    "teal_mid":    "rgba(0, 212, 170, 0.35)",
    "orange":      "#F97316",
    "orange_dim":  "rgba(249, 115, 22, 0.15)",
    "blue":        "#3B82F6",
    "red":         "#EF4444",
    "red_dim":     "rgba(239, 68, 68, 0.15)",
    "green":       "#22C55E",
    "green_dim":   "rgba(34, 197, 94, 0.15)",
    "yellow":      "#EAB308",
    "bg_base":     "#08101F",
    "bg_surface":  "#0F1A2E",
    "bg_card":     "#14243D",
    "text_primary":"#E2E8F0",
    "text_muted":  "#94A3B8",
    "grid":        "rgba(148, 163, 184, 0.08)",
    "border":      "rgba(0, 212, 170, 0.15)",
}

PALETA_ACTIVOS = [
    "#00D4AA", "#3B82F6", "#F97316", "#A78BFA",
    "#34D399", "#F472B6", "#FBBF24", "#60A5FA",
]

LAYOUT_BASE = dict(
    paper_bgcolor=COLORES["bg_surface"],
    plot_bgcolor=COLORES["bg_base"],
    font=dict(family="'IBM Plex Mono', 'Courier New', monospace", color=COLORES["text_primary"], size=11),
    margin=dict(l=52, r=28, t=52, b=52),
    xaxis=dict(gridcolor=COLORES["grid"], linecolor=COLORES["border"], tickcolor=COLORES["text_muted"],
               tickfont=dict(size=10, color=COLORES["text_muted"]), showgrid=True, zeroline=False),
    yaxis=dict(gridcolor=COLORES["grid"], linecolor=COLORES["border"], tickcolor=COLORES["text_muted"],
               tickfont=dict(size=10, color=COLORES["text_muted"]), showgrid=True, zeroline=False),
    legend=dict(bgcolor="rgba(14,26,46,0.9)", bordercolor=COLORES["border"], borderwidth=1,
                font=dict(size=10, color=COLORES["text_muted"]), orientation="h", y=-0.2),
    hoverlabel=dict(bgcolor=COLORES["bg_card"], bordercolor=COLORES["border"],
                    font=dict(size=11, color=COLORES["text_primary"])),
    hovermode="x unified",
)


def _titulo(texto: str) -> dict:
    return dict(
        text=texto,
        font=dict(size=13, color=COLORES["text_primary"], family="'IBM Plex Mono', monospace"),
        x=0, xanchor="left", pad=dict(l=0, b=8),
    )


def grafico_distribucion_retornos(resultado: dict) -> go.Figure:
    retornos  = resultado["retornos_portafolio"]
    var_pct   = resultado["var_pct"]
    cvar_pct  = resultado["cvar_pct"]
    confianza = resultado["nivel_confianza"]

    fig = go.Figure()
    fig.add_trace(go.Histogram(x=retornos, nbinsx=55, name="Distribución de retornos",
        marker=dict(color=COLORES["teal_mid"], line=dict(color=COLORES["teal"], width=0.5)),
        opacity=0.85, hovertemplate="Retorno: %{x:.3%}<br>Frecuencia: %{y}<extra></extra>"))

    x_loss = retornos[retornos <= var_pct]
    if len(x_loss) > 0:
        fig.add_trace(go.Histogram(x=x_loss, nbinsx=18,
            name=f"Zona de pérdida ({(1-confianza):.0%})",
            marker=dict(color=COLORES["red_dim"], line=dict(color=COLORES["red"], width=0.5)),
            opacity=0.9, hovertemplate="Retorno: %{x:.3%}<extra>Zona de pérdida</extra>"))

    fig.add_vline(x=var_pct, line_color=COLORES["orange"], line_width=1.5, line_dash="dash",
        annotation=dict(text=f"VaR {confianza:.0%}<br><b>{var_pct:.3%}</b>",
            font=dict(size=10, color=COLORES["orange"]), bgcolor=COLORES["bg_card"],
            bordercolor=COLORES["orange"], borderwidth=1, borderpad=4),
        annotation_position="top right")

    fig.add_vline(x=cvar_pct, line_color=COLORES["red"], line_width=1.5, line_dash="dot",
        annotation=dict(text=f"CVaR<br><b>{cvar_pct:.3%}</b>",
            font=dict(size=10, color=COLORES["red"]), bgcolor=COLORES["bg_card"],
            bordercolor=COLORES["red"], borderwidth=1, borderpad=4),
        annotation_position="top left")

    layout = {**LAYOUT_BASE}
    layout["title"]   = _titulo("Distribución de Retornos del Portafolio")
    layout["xaxis"]   = {**LAYOUT_BASE["xaxis"], "tickformat": ".1%", "title": dict(text="Retorno diario", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["yaxis"]   = {**LAYOUT_BASE["yaxis"], "title": dict(text="Frecuencia", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["height"]  = 420
    layout["bargap"]  = 0.04
    layout["hovermode"] = "x"
    fig.update_layout(**layout)
    return fig


def grafico_precios_historicos(resultado: dict) -> go.Figure:
    fechas       = resultado["fechas"]
    retornos_ind = resultado["retornos_individuales"]

    fig = go.Figure()
    for i, (ticker, retornos) in enumerate(retornos_ind.items()):
        precio = 100 * np.exp(np.cumsum(retornos))
        color  = PALETA_ACTIVOS[i % len(PALETA_ACTIVOS)]
        fig.add_trace(go.Scatter(x=fechas[1:], y=precio, mode="lines", name=ticker,
            line=dict(color=color, width=1.5),
            hovertemplate=f"<b>{ticker}</b><br>%{{x|%d %b %Y}}<br>Índice: %{{y:.1f}}<extra></extra>",
            fill="tozeroy",
            fillcolor=f"rgba{tuple(list(int(color.lstrip('#')[j:j+2], 16) for j in (0, 2, 4)) + [0.04])}"))

    fig.add_hline(y=100, line_dash="dash", line_color=COLORES["text_muted"], line_width=1, opacity=0.5,
        annotation=dict(text="base 100", font=dict(size=9, color=COLORES["text_muted"]), xanchor="right"),
        annotation_position="right")

    layout = {**LAYOUT_BASE}
    layout["title"]  = _titulo("Evolución de Precios (Base 100)")
    layout["xaxis"]  = {**LAYOUT_BASE["xaxis"], "title": dict(text="Fecha", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["yaxis"]  = {**LAYOUT_BASE["yaxis"], "title": dict(text="Precio indexado", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["height"] = 380
    fig.update_layout(**layout)
    return fig


def grafico_retornos_tiempo(resultado: dict) -> go.Figure:
    retornos = resultado["retornos_portafolio"]
    fechas   = resultado["fechas"]
    var_pct  = resultado["var_pct"]

    colores_barra = [COLORES["red"] if r < var_pct else COLORES["teal"] for r in retornos]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=fechas[1:], y=retornos,
        marker=dict(color=colores_barra, opacity=0.75, line=dict(width=0)),
        name="Retorno diario",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Retorno: %{y:.3%}<extra></extra>"))

    fig.add_hrect(y0=min(retornos) * 1.05, y1=var_pct,
        fillcolor=COLORES["red_dim"], line_width=0,
        annotation=dict(text="Zona VaR", font=dict(size=9, color=COLORES["red"]), xanchor="left"),
        annotation_position="top left")

    fig.add_hline(y=var_pct, line_color=COLORES["orange"], line_dash="dash", line_width=1.2,
        annotation=dict(text=f"VaR = {var_pct:.2%}",
            font=dict(size=10, color=COLORES["orange"]), bgcolor=COLORES["bg_card"],
            bordercolor=COLORES["orange"], borderwidth=1, borderpad=4, xanchor="right"),
        annotation_position="right")

    layout = {**LAYOUT_BASE}
    layout["title"]  = _titulo("Retornos Diarios del Portafolio")
    layout["xaxis"]  = {**LAYOUT_BASE["xaxis"], "title": dict(text="Fecha", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["yaxis"]  = {**LAYOUT_BASE["yaxis"], "tickformat": ".1%", "title": dict(text="Retorno diario", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["height"] = 360
    layout["hovermode"] = "x"
    fig.update_layout(**layout)
    return fig


def grafico_composicion(pesos: dict) -> go.Figure:
    tickers = list(pesos.keys())
    valores = list(pesos.values())

    fig = go.Figure(go.Pie(
        labels=tickers, values=valores, hole=0.52,
        marker=dict(colors=PALETA_ACTIVOS[:len(tickers)], line=dict(color=COLORES["bg_surface"], width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, family="'IBM Plex Mono', monospace", color=COLORES["text_primary"]),
        hovertemplate="<b>%{label}</b><br>Peso: %{value:.1%}<extra></extra>",
        direction="clockwise", sort=True,
    ))
    fig.add_annotation(text=f"<b>{len(tickers)}</b><br><span style='font-size:9px'>activos</span>",
        x=0.5, y=0.5, font=dict(size=16, color=COLORES["text_primary"]),
        showarrow=False, xanchor="center", yanchor="middle")

    layout = {**LAYOUT_BASE}
    layout["title"]       = _titulo("Composición del Portafolio")
    layout["height"]      = 360
    layout["showlegend"]  = False
    layout.pop("xaxis", None)
    layout.pop("yaxis", None)
    fig.update_layout(**layout)
    return fig


def grafico_correlacion(resultado: dict) -> go.Figure:
    retornos_ind = resultado["retornos_individuales"]

    if len(retornos_ind) < 2:
        fig = go.Figure()
        fig.add_annotation(text="Se necesitan ≥ 2 activos para calcular correlación",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=12, color=COLORES["text_muted"]))
        layout = {**LAYOUT_BASE}
        layout["height"] = 300
        layout.pop("xaxis", None); layout.pop("yaxis", None)
        fig.update_layout(**layout)
        return fig

    df_ret = pd.DataFrame(retornos_ind)
    corr   = df_ret.corr()
    colorscale = [[0.0, COLORES["red"]], [0.25, "#7F3F3F"], [0.5, COLORES["bg_card"]], [0.75, "#1A5E4A"], [1.0, COLORES["teal"]]]

    fig = go.Figure(go.Heatmap(
        z=corr.values, x=corr.columns.tolist(), y=corr.index.tolist(),
        colorscale=colorscale, zmid=0, zmin=-1, zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="<b>%{text}</b>",
        textfont=dict(size=11, family="'IBM Plex Mono', monospace"),
        hovertemplate="<b>%{y} × %{x}</b><br>Correlación: %{z:.3f}<extra></extra>",
        colorbar=dict(thickness=10, tickfont=dict(size=9, color=COLORES["text_muted"]),
            outlinecolor=COLORES["border"], outlinewidth=1, tickformat=".1f"),
    ))

    layout = {**LAYOUT_BASE}
    layout["title"]  = _titulo("Correlación entre Activos")
    layout["height"] = 360
    layout["xaxis"]  = {**LAYOUT_BASE["xaxis"], "side": "bottom", "showgrid": False}
    layout["yaxis"]  = {**LAYOUT_BASE["yaxis"], "autorange": "reversed", "showgrid": False}
    layout["hovermode"] = "closest"
    fig.update_layout(**layout)
    return fig


def grafico_monitor_semanal(
    declaracion: dict,
    retornos_acumulados: list,
    estado: str = "EN_CURSO",
    var_usd: float = None,
    fechas: list = None,
) -> go.Figure:
    """
    Gráfico de monitoreo semanal. Muestra:
    - Línea de pérdida acumulada del portafolio día a día
    - Línea horizontal del VaR declarado (límite)
    - Color del área según estado (verde/rojo/amarillo)
    """
    var_semanal_usd = var_usd if var_usd is not None else declaracion.get("var_semanal_usd", 0)
    fecha_inicio    = declaracion.get("fecha_inicio", "")
    fecha_fin       = declaracion.get("fecha_fin", "")

    fig = go.Figure()

    # Si no hay datos reales aún, mostrar solo el marco
    if not retornos_acumulados:
        # Proyección vacía con los 5 días de la semana como labels
        dias_labels = ["Lun", "Mar", "Mié", "Jue", "Vie"]

        fig.add_hline(
            y=var_semanal_usd,
            line_color=COLORES["orange"],
            line_dash="dash",
            line_width=2,
            annotation=dict(
                text=f"VaR Semanal = ${var_semanal_usd:,.2f} USD",
                font=dict(size=11, color=COLORES["orange"]),
                bgcolor=COLORES["bg_card"],
                bordercolor=COLORES["orange"],
                borderwidth=1,
                borderpad=4,
                xanchor="right",
            ),
            annotation_position="right",
        )

        fig.add_annotation(
            text=f"⏳ Semana aún no iniciada<br>{fecha_inicio} → {fecha_fin}",
            xref="paper", yref="paper", x=0.5, y=0.5,
            font=dict(size=13, color=COLORES["text_muted"]),
            showarrow=False, xanchor="center", yanchor="middle",
            bgcolor=COLORES["bg_card"],
            bordercolor=COLORES["border"],
            borderpad=8,
        )

    else:
        # Convertir retornos acumulados a pérdidas en USD
        valor_portafolio = declaracion.get("valor_portafolio", 100_000)
        perdidas_usd = [abs(min(r, 0)) * valor_portafolio for r in retornos_acumulados]

        etiquetas = fechas if fechas else [f"Día {i+1}" for i in range(len(perdidas_usd))]

        # Color de línea según estado
        if estado == "VIOLADO":
            color_linea = COLORES["red"]
            fill_color  = "rgba(239,68,68,0.12)"
        elif estado == "RESPETADO":
            color_linea = COLORES["green"]
            fill_color  = "rgba(34,197,94,0.10)"
        else:
            color_linea = COLORES["teal"]
            fill_color  = COLORES["teal_dim"]

        # Área de pérdida acumulada
        fig.add_trace(go.Scatter(
            x=etiquetas,
            y=perdidas_usd,
            mode="lines+markers",
            name="Pérdida acumulada real",
            line=dict(color=color_linea, width=2.5),
            marker=dict(size=8, color=color_linea, line=dict(color=COLORES["bg_base"], width=1.5)),
            fill="tozeroy",
            fillcolor=fill_color,
            hovertemplate="<b>%{x}</b><br>Pérdida acum: $%{y:,.2f}<extra></extra>",
        ))

        # Línea del VaR
        fig.add_hline(
            y=var_semanal_usd,
            line_color=COLORES["orange"],
            line_dash="dash",
            line_width=2,
            annotation=dict(
                text=f"VaR Límite = ${var_semanal_usd:,.2f}",
                font=dict(size=11, color=COLORES["orange"]),
                bgcolor=COLORES["bg_card"],
                bordercolor=COLORES["orange"],
                borderwidth=1,
                borderpad=4,
                xanchor="right",
            ),
            annotation_position="right",
        )

        # Zona de peligro (área roja arriba del VaR)
        max_y = max(max(perdidas_usd) * 1.3, var_semanal_usd * 1.5)
        fig.add_hrect(
            y0=var_semanal_usd, y1=max_y,
            fillcolor="rgba(239,68,68,0.06)",
            line_width=0,
            annotation=dict(text="ZONA DE VIOLACIÓN", font=dict(size=9, color=COLORES["red"]), xanchor="left"),
            annotation_position="top left",
        )

        # Marcadores de violación
        for i, (fecha, perdida) in enumerate(zip(etiquetas, perdidas_usd)):
            if perdida > var_semanal_usd:
                fig.add_annotation(
                    x=fecha, y=perdida,
                    text="⚠ VIOLACIÓN",
                    font=dict(size=10, color=COLORES["red"]),
                    bgcolor=COLORES["bg_card"],
                    bordercolor=COLORES["red"],
                    borderpad=4,
                    showarrow=True,
                    arrowcolor=COLORES["red"],
                    ay=-40,
                )

    # Título según estado
    titulos = {
        "EN_CURSO":  "📡 Monitor Semanal — En Curso",
        "RESPETADO": "✅ Monitor Semanal — VaR Respetado",
        "VIOLADO":   "🔴 Monitor Semanal — VaR Violado",
    }

    layout = {**LAYOUT_BASE}
    layout["title"]  = _titulo(titulos.get(estado, "Monitor Semanal"))
    layout["height"] = 400
    layout["xaxis"]  = {**LAYOUT_BASE["xaxis"],
        "title": dict(text="Día de la semana", font=dict(size=10, color=COLORES["text_muted"]))}
    layout["yaxis"]  = {**LAYOUT_BASE["yaxis"],
        "title": dict(text="Pérdida acumulada (USD)", font=dict(size=10, color=COLORES["text_muted"])),
        "tickprefix": "$", "tickformat": ",.0f"}
    layout["hovermode"] = "x unified"
    layout["showlegend"] = True

    fig.update_layout(**layout)
    return fig
