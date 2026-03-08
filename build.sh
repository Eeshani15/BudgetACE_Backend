#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Create superuser if it doesn't exist (safe)
python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', email)

if email and password:
    if not User.objects.filter(email=email).exists():
        User.objects.create_superuser(username=username, email=email, password=password)
        print('✅ Superuser created:', email)
    else:
        print('ℹ️ Superuser already exists:', email)
else:
    print('⚠️ DJANGO_SUPERUSER_EMAIL/PASSWORD not set, skipping superuser creation')
"