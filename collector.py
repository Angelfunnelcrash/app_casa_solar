"""
Solar Monitor - Collector
Recoge datos del inversor Sungrow SH6.0RS via Modbus TCP (local)
y los guarda en PostgreSQL cada 60 segundos.
Cuando la API de iSolarCloud esté aprobada, también consultará el Wibeee.
"""

import socket
import struct
import time
import json
from datetime import datetime
from typing import Optional

# ============================================================================
# CONFIG — editable aquí o vía variables de entorno
# ============================================================================
SUNGROW_HOST = "192.168.3.39"
SUNGROW_PORT = 502
DEVICE_ID = 1  # ID Modbus del inversor (por defecto = 1)

# PostgreSQL
PG_HOST = "localhost"
PG_PORT = 5432
PG_USER = "solar"
PG_PASSWORD = "solar123"
PG_DATABASE = "solar_monitor"

POLL_INTERVAL = 60  # segundos entre lecturas

# ============================================================================
# REGISTROS MODBUS — mapa estándar para Sungrow SH series
# (verificar con el manual del equipo si los valores no cuadran)
# ============================================================================
# Registro → (nombre, factor de conversión, unidad)
REGISTERS = {
    # Potencia activa total (W)
    1300: ("total_dc_power_w", 1, "W"),
    # Energía total generada (kWh) — 2 registros uint32 (high/low)
    1303: ("total_energy_kwh", 1, "kWh"),
    # Tensión fase L1 (V)
    1304: ("voltage_l1_v", 0.1, "V"),
    # Tensión fase L2 (V)
    1305: ("voltage_l2_v", 0.1, "V"),
    # Tensión fase L3 (V)
    1306: ("voltage_l3_v", 0.1, "V"),
    # Corriente fase L1 (A)
    1307: ("current_l1_a", 0.01, "A"),
    # Corriente fase L2 (A)
    1308: ("current_l2_a", 0.01, "A"),
    # Corriente fase L3 (A)
    1309: ("current_l3_a", 0.01, "A"),
    # Potencia activa total AC (W)
    1313: ("total_ac_power_w", 1, "W"),
    # Estado del inversor (0=off, 1=on, 2=standby, etc.)
    5000: ("device_status", 1, ""),
}


def read_modbus_register(host: str, port: int, device_id: int, address: int, count: int = 1) -> Optional[int]:
    """
    Lee un registro (o varios) del inversor vía Modbus TCP.
    Devuelve None si falla.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))

        # Modbus PDU: función 0x03 (Read Holding Registers)
        # Frame: [device_id(1)] [function(1)] [address(2)] [count(2)] [CRC(2)]
        request = struct.pack(">BBHH", device_id, 0x03, address, count)
        # Añadir CRC16 Modbus
        crc = calc_crc16(request)
        request += struct.pack("<H", crc)

        sock.send(request)
        # Respuesta: [device_id] [func] [byte_count] [data...] [CRC]
        response = sock.recv(1024)
        sock.close()

        if len(response) < 9:
            return None

        byte_count = response[2]
        data = response[3:3 + byte_count]

        if count == 1:
            return struct.unpack(">H", data[:2])[0]
        else:
            # Varios registros (uint32: 2 registros big-endian)
            return struct.unpack(">I", data[:4])[0]

    except Exception as e:
        print(f"  [Modbus] Error leyendo reg {address}: {e}")
        return None


def calc_crc16(data: bytes) -> int:
    """Calcula CRC16 Modbus (RTU)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def read_modbus_u32(host: str, port: int, device_id: int, address: int) -> Optional[float]:
    """Lee un uint32 (2 registros) y devuelve float."""
    value = read_modbus_register(host, port, device_id, address, count=2)
    if value is not None:
        return float(value)
    return None


def read_sungrow_data() -> dict:
    """
    Lee todos los registros configurados del inversor Sungrow.
    Devuelve un dict con los valores.
    """
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "device": "sungrow_sh6",
        "error": None
    }

    print(f"  Leyendo Sungrow {SUNGROW_HOST}:{SUNGROW_PORT}...")

    # Leer registros de un soloholding
    for reg, (name, factor, unit) in REGISTERS.items():
        if reg in (1303,):  # 1303 es uint32 (2 registros)
            value = read_modbus_u32(SUNGROW_HOST, SUNGROW_PORT, DEVICE_ID, reg)
        else:
            raw = read_modbus_register(SUNGROW_HOST, SUNGROW_PORT, DEVICE_ID, reg)
            if raw is not None:
                value = round(raw * factor, 3)
            else:
                value = None

        data[name] = value
        if value is not None:
            print(f"    {name} = {value} {unit}")
        else:
            print(f"    {name} = N/A")

    return data


def save_to_postgres(data: dict) -> bool:
    """Guarda los datos en PostgreSQL."""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DATABASE
        )
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO solar_readings (
                timestamp, device,
                total_dc_power_w, total_ac_power_w,
                voltage_l1_v, voltage_l2_v, voltage_l3_v,
                current_l1_a, current_l2_a, current_l3_a,
                total_energy_kwh, device_status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            data["timestamp"],
            data["device"],
            data.get("total_dc_power_w"),
            data.get("total_ac_power_w"),
            data.get("voltage_l1_v"),
            data.get("voltage_l2_v"),
            data.get("voltage_l3_v"),
            data.get("current_l1_a"),
            data.get("current_l2_a"),
            data.get("current_l3_a"),
            data.get("total_energy_kwh"),
            data.get("device_status"),
        ))

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except ImportError:
        print("  [ERROR] psycopg2 no instalado. Instala con: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"  [ERROR] PostgreSQL: {e}")
        return False


def save_json(data: dict, filepath: str = "latest_reading.json"):
    """Guarda la última lectura como JSON (backup si PostgreSQL no está)."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def main():
    print("=" * 60)
    print("Solar Monitor — Collector (Sungrow SH6.0RS)")
    print(f"  Host: {SUNGROW_HOST}:{SUNGROW_PORT}")
    print(f"  Poll interval: {POLL_INTERVAL}s")
    print("=" * 60)

    cycle = 1
    while True:
        print(f"\n[Ciclo #{cycle}] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        data = read_sungrow_data()

        if data["error"] is None:
            save_json(data)
            pg_ok = save_to_postgres(data)
            if pg_ok:
                print("  [OK] Datos guardados en PostgreSQL")
            else:
                print("  [OK] Datos guardados en JSON (backup)")
        else:
            print(f"  [ERROR] {data['error']}")

        cycle += 1
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()