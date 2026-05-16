#!/bin/bash
# Solar Monitor — Setup de PostgreSQL
# Ejecutar UNA vez antes de arrancar el collector

set -e

PG_USER="${PG_USER:-solar}"
PG_PASS="${PG_PASS:-solar123}"
PG_DB="${PG_DB:-solar_monitor}"

echo "==> Creando usuario PostgreSQL: $PG_USER"
sudo -u postgres psql -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASS';" 2>/dev/null || echo "  (usuario ya existe, se salta)"
sudo -u postgres psql -c "CREATE DATABASE $PG_DB OWNER $PG_USER;" 2>/dev/null || echo "  (base de datos ya existe, se salta)"

echo "==> Cargando esquema..."
sudo -u postgres psql -d "$PG_DB" -f schema.sql

echo ""
echo "==> Asignando permisos..."
sudo -u postgres psql -d "$PG_DB" -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DB TO $PG_USER;"
sudo -u postgres psql -d "$PG_DB" -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $PG_USER;"
sudo -u postgres psql -d "$PG_DB" -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $PG_USER;"

echo ""
echo "==> ¡Listo! Base de datos configurada."
echo "    Para probar manualmente:"
echo "    psql -U $PG_USER -d $PG_DB -c 'SELECT * FROM solar_readings LIMIT 1;'"