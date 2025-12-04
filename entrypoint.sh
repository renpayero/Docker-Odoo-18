#!/bin/bash
set -euo pipefail

ODOO_DB_NAME="${ODOO_DB_NAME:-${POSTGRES_DB:-odoo}}"
ODOO_DB_HOST="${ODOO_DB_HOST:-${DB_HOST:-db}}"
ODOO_DB_PORT="${ODOO_DB_PORT:-${DB_PORT:-5432}}"
ODOO_DB_USER="${ODOO_DB_USER:-${DB_USER:-odoo}}"
ODOO_DB_PASSWORD="${ODOO_DB_PASSWORD:-${DB_PASSWORD:-odoo}}"

wait_for_database() {
    until PGPASSWORD="$ODOO_DB_PASSWORD" pg_isready -h "$ODOO_DB_HOST" -p "$ODOO_DB_PORT" -d "$ODOO_DB_NAME" -U "$ODOO_DB_USER" >/dev/null 2>&1; do
        echo "Waiting for PostgreSQL at $ODOO_DB_HOST:$ODOO_DB_PORT..."
        sleep 2
    done
}

needs_bootstrap() {
    PGPASSWORD="$ODOO_DB_PASSWORD" psql "postgresql://$ODOO_DB_USER@$ODOO_DB_HOST:$ODOO_DB_PORT/$ODOO_DB_NAME" -tAc "SELECT to_regclass('public.ir_module_module')" | grep -q "ir_module_module"
}

wait_for_database

if ! needs_bootstrap; then
    echo "Initializing database '$ODOO_DB_NAME' with base module..."
    odoo \
        --db_host="$ODOO_DB_HOST" \
        --db_port="$ODOO_DB_PORT" \
        --db_user="$ODOO_DB_USER" \
        --db_password="$ODOO_DB_PASSWORD" \
        -d "$ODOO_DB_NAME" \
        -i base \
        --stop-after-init
fi

exec /entrypoint.sh "$@"
