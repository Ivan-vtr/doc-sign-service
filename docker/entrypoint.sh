#!/bin/sh
set -e

echo "==> Waiting for database at ${DB_HOST:-db}:${DB_PORT:-5432}..."
while ! python -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(('${DB_HOST:-db}', ${DB_PORT:-5432}))
    s.close()
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    sleep 1
done
echo "==> Database is ready"

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Creating superuser (if not exists)..."
python manage.py shell -c "
from django.contrib.auth.models import User
from app.infrastructure.persistence.models import UserProfile
import os
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
iin = os.environ.get('DJANGO_SUPERUSER_IIN', '000000000000')
if not User.objects.filter(username=username).exists():
    user = User.objects.create_superuser(username, email, password)
    UserProfile.objects.create(user=user, iin=iin, full_name=username, signer_type='individual')
    print(f'Superuser \"{username}\" created')
else:
    print(f'Superuser \"{username}\" already exists')
"

echo "==> Starting server..."
exec "$@"
