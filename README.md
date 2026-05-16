# Solar Monitor — Sungrow SH6.0RS + Wibeee Mono

Dashboard local para monitorizar producción solar y consumo eléctrico.

## Estructura de archivos

```
solar-monitor/
├── collector.py       # Recoge datos del inversor y los guarda en PostgreSQL
├── dashboard.py       # Dashboard web (Streamlit)
├── schema.sql         # Esquema de la base de datos PostgreSQL
├── setup_pg.sh        # Script para configurar PostgreSQL (ejecutar 1 vez)
├── requirements.txt   # Dependencias Python
└── README.md          # Este archivo
```

## Requisitos

- Python 3.8+
- PostgreSQL 13+
- Acceso de red al inversor Sungrow `192.168.3.39:502`

## Instalación

### 1. Dependencias Python

```bash
pip install -r requirements.txt
# o para dashboard y todo:
pip install psycopg2-binary streamlit pandas plotly
```

### 2. PostgreSQL

```bash
# Crear usuario y base de datos
chmod +x setup_pg.sh
./setup_pg.sh

# O manualmente:
sudo -u postgres psql -c "CREATE USER solar WITH PASSWORD 'solar123';"
sudo -u postgres psql -c "CREATE DATABASE solar_monitor OWNER solar;"
sudo -u postgres psql -d solar_monitor -f schema.sql
```

### 3. Configuración

Edita las constantes al inicio de `collector.py` si quieres cambiar:
- IP del inversor (por defecto `192.168.3.39`)
- Puerto Modbus (por defecto `502`)
- Intervalo de polling (por defecto `60` segundos)
- Credenciales PostgreSQL

## Uso

### Arrancar el collector (recoge datos cada 60s)

```bash
python collector.py
```

Se ejecutará en segundo plano indefinidamente, guardando datos en PostgreSQL.

### Arrancar el dashboard

```bash
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0
```

Luego abre: **http://localhost:8501**

## Modo test (sin inversor real)

Si quieres probar sin tener el inversor conectado, edita `collector.py` y
sustituye la función `read_sungrow_data()` por esta versión mock:

```python
def read_sungrow_data() -> dict:
    import random
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "device": "sungrow_sh6",
        "error": None,
        "total_dc_power_w": round(random.uniform(0, 6000), 2),
        "total_ac_power_w": round(random.uniform(0, 5900), 2),
        "voltage_l1_v": round(random.uniform(220, 240), 2),
        "voltage_l2_v": round(random.uniform(220, 240), 2),
        "voltage_l3_v": round(random.uniform(220, 240), 2),
        "current_l1_a": round(random.uniform(0, 25), 2),
        "current_l2_a": round(random.uniform(0, 25), 2),
        "current_l3_a": round(random.uniform(0, 25), 2),
        "total_energy_kwh": round(random.uniform(0, 9999), 3),
        "device_status": 1,
    }
```

## Notas

- **Wibeee**: actualmente gestionado por Iberdrola (API no disponible aún).
  Cuando Iberdrola active el acceso API, se añadirá al collector.
- **Sungrow API**: solicitud pending en iSolarCloud. Cuando aprueben,
  se podrá usar la API cloud además del Modbus local.
- **Modo oscuro**: el dashboard usa tema oscuro por defecto.
- **Auto-refresh**: el dashboard actualiza cada 30s automáticamente.