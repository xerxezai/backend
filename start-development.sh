#!/bin/bash
set -e

echo "🔧 Starting Django Development Server..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
python << END
import sys
import time
import psycopg2
from psycopg2 import OperationalError

def wait_for_db():
    """Wait for database to become available"""
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        try:
            conn = psycopg2.connect(
                dbname="${POSTGRES_DB:-xerxez_db}",
                user="${POSTGRES_USER:-xerxez_user}",
                password="${POSTGRES_PASSWORD:-xerxez_pass}",
                host="postgres",
                port="5432"
            )
            conn.close()
            print("✅ Database is ready!")
            return True
        except OperationalError:
            attempt += 1
            print(f"📡 Database not ready, attempt {attempt}/{max_attempts}")
            time.sleep(2)
    
    print("❌ Database failed to become ready")
    sys.exit(1)

wait_for_db()
END

# Run migrations
echo "📊 Running database migrations..."
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo "👤 Creating superuser if needed..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('✅ Superuser created: admin/admin123')
else:
    print('✅ Superuser already exists')
END

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Load initial data (optional)
echo "📋 Loading initial data..."
python manage.py shell << END
# You can add initial data loading here if needed
print('✅ Initial data loaded')
END

echo "🚀 Starting Django development server..."
echo "🌐 Backend will be available at: http://localhost:8000"
echo "📋 API documentation at: http://localhost:8000/docs/"
echo "🔧 Admin interface at: http://localhost:8000/admin/"

# Start development server with hot reload
exec python manage.py runserver 0.0.0.0:8000