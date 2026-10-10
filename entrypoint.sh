#!/bin/sh
set -e

# Allow one-off commands (e.g., migrations in CI/CD) without starting Gunicorn.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

to_bool() {
    case "${1:-}" in
        1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
        *) return 1 ;;
    esac
}

# Run migrations (configurable for production workflows)
if to_bool "${RUN_MIGRATIONS_ON_STARTUP:-true}"; then
    echo "Running migrations..."
    python manage.py migrate --noinput
else
    echo "Skipping startup migrations (RUN_MIGRATIONS_ON_STARTUP=${RUN_MIGRATIONS_ON_STARTUP:-false})"
fi

# Collect static files (configurable for production workflows)
if to_bool "${RUN_COLLECTSTATIC_ON_STARTUP:-true}"; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
else
    echo "Skipping startup collectstatic (RUN_COLLECTSTATIC_ON_STARTUP=${RUN_COLLECTSTATIC_ON_STARTUP:-false})"
fi

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000