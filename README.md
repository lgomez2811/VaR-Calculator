# 📈 Proyecto VaR — Sistema de Medición de Riesgo de Mercado

Sistema para calcular el **Value at Risk (VaR)** de un portafolio usando simulación histórica, con interfaz gráfica en **Gradio**, pipeline orquestado con **Prefect** y almacenamiento en **DuckDB**.

---

## 🗂️ Estructura del proyecto

```
proyecto_var/
├── data/
│   └── portafolio.duckdb     # Base de datos DuckDB (se crea automáticamente)
├── notebooks/
│   └── exploracion.ipynb     # Análisis paso a paso
├── src/
│   ├── app.py                # ← PUNTO DE ENTRADA: interfaz Gradio
│   ├── pipeline.py           # Pipeline Prefect (Bronze → Silver → Gold)
│   └── graficos.py           # Gráficos interactivos con Plotly
├── pyproject.toml            # Configuración del proyecto para uv
└── README.md
```

---

## ⚙️ Instalación con uv

```bash
# 1. Instalar uv (si no lo tienes)
pip install uv

# 2. Crear entorno virtual e instalar dependencias
uv sync

# 3. Activar el entorno
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Mac/Linux
```

---

## 🚀 Cómo ejecutar

### Opción A — Solo la app (lo más simple)
```bash
python src/app.py
```
Abre en tu navegador: **http://localhost:7860**

### Opción B — Ver el pipeline en Prefect también
En una terminal aparte:
```bash
prefect server start
```
Abre: **http://localhost:4200** para ver las tareas corriendo en tiempo real.

Luego en otra terminal:
```bash
python src/app.py
```

---

## 🏗️ Arquitectura

| Capa | Herramienta | Qué hace |
|------|-------------|----------|
| **Bronze** | yfinance + DuckDB | Descarga precios crudos de Yahoo Finance |
| **Silver** | pandas + DuckDB | Limpia datos y calcula retornos logarítmicos |
| **Gold** | numpy + DuckDB | Calcula VaR histórico y CVaR del portafolio |
| **Orquestación** | Prefect | Garantiza que las 3 capas corran en orden |
| **Visualización** | Plotly + Gradio | Interfaz web con gráficos interactivos |

---

## 🔍 Ver datos en DBeaver

1. Abre DBeaver
2. Nueva conexión → **DuckDB**
3. Selecciona el archivo: `data/portafolio.duckdb`
4. Verás 3 schemas: **bronze**, **silver**, **gold**

---

> ⚠️ *Proyecto académico. El VaR histórico no garantiza resultados futuros.*
