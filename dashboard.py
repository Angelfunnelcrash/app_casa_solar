"""
Solar Monitor — Dashboard
Requiere: streamlit, pandas, psycopg2-binary, plotly
Ejecutar con: streamlit run dashboard.py --server.port 8501
"""

import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

# ============================================================================
# CONFIG
# ============================================================================
PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "solar"
PG_PASSWORD = "solar123"
PG_DATABASE = "solar_monitor"

REFRESH_INTERVAL = 30  # segundos entre refresh automático

# ============================================================================
# CONEXIÓN POSTGRESQL
# ============================================================================
@st.cache_data(ttl=30)
def load_data(hours: int = 24) -> pd.DataFrame:
    """Carga las últimas N horas de datos desde PostgreSQL."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            user=PG_USER, password=PG_PASSWORD,
            dbname=PG_DATABASE
        )

        query = """
            SELECT
                timestamp,
                device,
                total_ac_power_w    AS potencia_w,
                voltage_l1_v         AS tension_l1_v,
                voltage_l2_v         AS tension_l2_v,
                voltage_l3_v         AS tension_l3_v,
                current_l1_a         AS corriente_l1_a,
                current_l2_a         AS corriente_l2_a,
                current_l3_a         AS corriente_l3_a,
                total_energy_kwh     AS energia_kwh,
                device_status
            FROM solar_readings
            WHERE timestamp > NOW() - INTERVAL '%s hours'
            ORDER BY timestamp ASC
        """

        df = pd.read_sql(query % hours, conn)
        conn.close()

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    except Exception as e:
        st.error(f"Error conectando a PostgreSQL: {e}")
        return pd.DataFrame()


def get_current_values() -> dict:
    """Obtiene los últimos valores disponibles."""
    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            user=PG_USER, password=PG_PASSWORD,
            dbname=PG_DATABASE
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                timestamp, device,
                total_ac_power_w, total_dc_power_w,
                voltage_l1_v, voltage_l2_v, voltage_l3_v,
                current_l1_a, current_l2_a, current_l3_a,
                total_energy_kwh, device_status,
                consumption_w
            FROM solar_readings
            ORDER BY timestamp DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        conn.close()

        if row:
            cols = ["timestamp","device","potencia_ac_w","potencia_dc_w",
                    "v_l1","v_l2","v_l3","i_l1","i_l2","i_l3","energia_kwh","status","consumo_w"]
            return dict(zip(cols, row))
        return {}

    except Exception:
        return {}


# ============================================================================
# ESTILOS
# ============================================================================
st.set_page_config(
    page_title="Solar Monitor",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .metric-box {
        background: #0d1117;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
        margin: 0.5rem 0;
    }
    .metric-label {
        color: #8b949e;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        color: #58a6ff;
        font-size: 2.2rem;
        font-weight: 700;
    }
    .metric-unit {
        color: #8b949e;
        font-size: 0.9rem;
    }
    .section-title {
        color: #c9d1d9;
        font-size: 1.1rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# HEADER
# ============================================================================
st.title("☀️ Solar Monitor")
st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')} — "
           f"Auto-refresh cada {REFRESH_INTERVAL}s")


# ============================================================================
# VALORES ACTUALES (métricas grandes)
# ============================================================================
current = get_current_values()

if current:
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.markdown('<div class="metric-box">'
                    '<div class="metric-label">Potencia AC</div>'
                    f'<div class="metric-value">{current.get("potencia_ac_w") or "—"}</div>'
                    '<div class="metric-unit">W</div></div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="metric-box">'
                    '<div class="metric-label">Potencia DC</div>'
                    f'<div class="metric-value">{current.get("potencia_dc_w") or "—"}</div>'
                    '<div class="metric-unit">W</div></div>', unsafe_allow_html=True)

    with col3:
        st.markdown('<div class="metric-box">'
                    '<div class="metric-label">Energía Total</div>'
                    f'<div class="metric-value">{current.get("energia_kwh") or "—"}</div>'
                    '<div class="metric-unit">kWh</div></div>', unsafe_allow_html=True)

    with col4:
        status_map = {0: "Off", 1: "On", 2: "Standby"}
        status_text = status_map.get(current.get("status"), current.get("status") or "—")
        st.markdown('<div class="metric-box">'
                    '<div class="metric-label">Estado</div>'
                    f'<div class="metric-value" style="font-size:1.5rem">{status_text}</div>'
                    '<div class="metric-unit">Inversor</div></div>', unsafe_allow_html=True)

    with col5:
        st.markdown('<div class="metric-box">'
                    '<div class="metric-label">Consumo Wibeee</div>'
                    f'<div class="metric-value">{current.get("consumo_w") or "—"}</div>'
                    '<div class="metric-unit">W</div></div>', unsafe_allow_html=True)

else:
    st.info("⏳ Cargando datos... Asegúrate de que el collector está corriendo "
            "y de que PostgreSQL está configurado.")


# ============================================================================
# GRÁFICAS
# ============================================================================
st.markdown('<div class="section-title">📈 Producción Solar (últimas 24h)</div>', unsafe_allow_html=True)

df = load_data(hours=24)

if not df.empty and "potencia_w" in df.columns:
    df_solar = df[df["device"] == "sungrow_sh6"].copy()

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.08,
        subplot_titles=("Potencia (W)", "Tensión Fase L1 (V)")
    )

    # Potencia
    fig.add_trace(go.Scatter(
        x=df_solar["timestamp"],
        y=df_solar["potencia_w"],
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(88, 166, 255, 0.15)",
        line=dict(color="#58a6ff", width=1.5),
        name="Potencia AC (W)"
    ), row=1, col=1)

    # Tensión L1
    if "tension_l1_v" in df_solar.columns:
        fig.add_trace(go.Scatter(
            x=df_solar["timestamp"],
            y=df_solar["tension_l1_v"],
            mode="lines",
            line=dict(color="#f0883e", width=1),
            name="Tensión L1 (V)"
        ), row=2, col=1)

    fig.update_layout(
        height=400,
        showlegend=False,
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        xaxis=dict(showgrid=True, gridcolor="#21262d"),
        yaxis=dict(showgrid=True, gridcolor="#21262d"),
        margin=dict(l=40, r=20, t=30, b=30)
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabla de datos recientes
    with st.expander("Ver datos recientes"):
        st.dataframe(
            df_solar[["timestamp","potencia_w","v_l1","v_l2","v_l3","i_l1","i_l2","i_l3","energia_kwh"]]
                     .tail(20)
                     .rename(columns={
                         "timestamp": "Fecha",
                         "potencia_w": "Pot (W)",
                         "v_l1": "V-L1", "v_l2": "V-L2", "v_l3": "V-L3",
                         "i_l1": "I-L1", "i_l2": "I-L2", "i_l3": "I-L3",
                         "energia_kwh": "Energía (kWh)"
                     }),
            use_container_width=True,
            hide_index=True
        )
else:
    st.warning("Sin datos aún — el collector necesita correr primero.")


# ============================================================================
# AUTO-REFRESH
# ============================================================================
time.sleep(REFRESH_INTERVAL)
st.rerun()