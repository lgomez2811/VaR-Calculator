"""
graficos.py
-----------
Funciones para crear gráficos interactivos con Plotly.
Cada función recibe el resultado del pipeline y retorna
una figura de Plotly lista para mostrar en Gradio.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


def grafico_distribucion_retornos(resultado: dict) -> go.Figure:
    """
    Histograma de retornos del portafolio con el VaR marcado.
    """
    retornos = resultado["retornos_portafolio"]
    var_pct = resultado["var_pct"]
    cvar_pct = resultado["cvar_pct"]
    confianza = resultado["nivel_confianza"]

    fig = go.Figure()

    # Histograma de retornos
    fig.add_trace(go.Histogram(
        x=retornos,
        nbinsx=50,
        name="Retornos del portafolio",
        marker_color="#4C72B0",
        opacity=0.75,
        hovertemplate="Retorno: %{x:.2%}<br>Frecuencia: %{y}<extra></extra>"
    ))

    # Línea del VaR
    fig.add_vline(
        x=var_pct,
        line_color="red",
        line_width=2,
        line_dash="dash",
        annotation_text=f"VaR {confianza:.0%} = {var_pct:.2%}",
        annotation_font_color="red",
        annotation_position="top right"
    )

    # Línea del CVaR
    fig.add_vline(
        x=cvar_pct,
        line_color="darkred",
        line_width=2,
        line_dash="dot",
        annotation_text=f"CVaR = {cvar_pct:.2%}",
        annotation_font_color="darkred",
        annotation_position="top left"
    )

    # Área de pérdida (izquierda del VaR)
    x_loss = retornos[retornos <= var_pct]
    if len(x_loss) > 0:
        fig.add_trace(go.Histogram(
            x=x_loss,
            nbinsx=15,
            name=f"Zona de pérdida ({(1-confianza):.0%})",
            marker_color="red",
            opacity=0.5,
            hovertemplate="Retorno: %{x:.2%}<extra></extra>"
        ))

    fig.update_layout(
        title="📊 Distribución de Retornos del Portafolio",
        xaxis_title="Retorno Diario",
        yaxis_title="Frecuencia",
        xaxis_tickformat=".1%",
        legend=dict(orientation="h", y=-0.2),
        height=420,
        hovermode="x",
        bargap=0.05,
        template="plotly_white"
    )

    return fig


def grafico_precios_historicos(resultado: dict) -> go.Figure:
    """
    Líneas de precios históricos de cada activo (normalizados a 100).
    """
    fechas = resultado["fechas"]
    retornos_ind = resultado["retornos_individuales"]

    fig = go.Figure()

    colores = px.colors.qualitative.Set2

    for i, (ticker, retornos) in enumerate(retornos_ind.items()):
        # Convertir retornos log a precio indexado (base 100)
        precio_indexado = 100 * np.exp(np.cumsum(retornos))
        color = colores[i % len(colores)]

        fig.add_trace(go.Scatter(
            x=fechas[1:],  # el primero se pierde al calcular retornos
            y=precio_indexado,
            mode="lines",
            name=ticker,
            line=dict(color=color, width=2),
            hovertemplate=f"{ticker}<br>Fecha: %{{x}}<br>Índice: %{{y:.1f}}<extra></extra>"
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="gray",
                  annotation_text="Base 100", annotation_position="right")

    fig.update_layout(
        title="📈 Evolución de Precios (Base 100)",
        xaxis_title="Fecha",
        yaxis_title="Precio Indexado (Base = 100)",
        legend=dict(orientation="h", y=-0.2),
        height=380,
        hovermode="x unified",
        template="plotly_white"
    )

    return fig


def grafico_retornos_tiempo(resultado: dict) -> go.Figure:
    """
    Retornos del portafolio a lo largo del tiempo.
    """
    retornos = resultado["retornos_portafolio"]
    fechas = resultado["fechas"]
    var_pct = resultado["var_pct"]

    colores = ["red" if r < var_pct else "#4C72B0" for r in retornos]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=fechas[1:],
        y=retornos,
        marker_color=colores,
        name="Retorno diario",
        hovertemplate="Fecha: %{x}<br>Retorno: %{y:.2%}<extra></extra>"
    ))

    fig.add_hline(
        y=var_pct,
        line_color="red",
        line_dash="dash",
        line_width=1.5,
        annotation_text=f"VaR = {var_pct:.2%}",
        annotation_position="right"
    )

    fig.update_layout(
        title="📉 Retornos Diarios del Portafolio en el Tiempo",
        xaxis_title="Fecha",
        yaxis_title="Retorno Diario",
        yaxis_tickformat=".1%",
        height=360,
        template="plotly_white"
    )

    return fig


def grafico_composicion(pesos: dict) -> go.Figure:
    """
    Gráfico de torta mostrando la composición del portafolio.
    """
    tickers = list(pesos.keys())
    valores = list(pesos.values())

    fig = go.Figure(go.Pie(
        labels=tickers,
        values=valores,
        hole=0.4,
        textinfo="label+percent",
        hovertemplate="%{label}<br>Peso: %{value:.1%}<extra></extra>"
    ))

    fig.update_layout(
        title="🥧 Composición del Portafolio",
        height=360,
        template="plotly_white"
    )

    return fig


def grafico_correlacion(resultado: dict) -> go.Figure:
    """
    Mapa de calor de correlaciones entre activos.
    """
    retornos_ind = resultado["retornos_individuales"]
    if len(retornos_ind) < 2:
        # Con un solo activo no hay correlación
        fig = go.Figure()
        fig.add_annotation(
            text="Se necesitan al menos 2 activos para la correlación",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False, font_size=14
        )
        fig.update_layout(height=300)
        return fig

    df_ret = pd.DataFrame(retornos_ind)
    corr = df_ret.corr()

    fig = go.Figure(go.Heatmap(
        z=corr.values,
        x=corr.columns.tolist(),
        y=corr.index.tolist(),
        colorscale="RdBu",
        zmid=0,
        text=[[f"{v:.2f}" for v in row] for row in corr.values],
        texttemplate="%{text}",
        hovertemplate="Activo X: %{x}<br>Activo Y: %{y}<br>Correlación: %{z:.2f}<extra></extra>"
    ))

    fig.update_layout(
        title="🔗 Correlación entre Activos",
        height=360,
        template="plotly_white"
    )

    return fig
