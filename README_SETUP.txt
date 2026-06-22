# AWS Data Management
# For S3 storage, add these to requirements/base.txt:
# boto3==1.26.0
# django-storages==1.14.0

# Then set in .env:
# USE_S3=True
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# AWS_S3_BUCKET=xerxez-storage
# AWS_S3_REGION=us-east-1

# PostgreSQL Database Setup Guide
# Database: xerxez_db
# User: xerxez_user
# Password: xerxez_password
# Host: localhost (or postgres if using Docker)
# Port: 5432

# To run with Docker:
# docker-compose up -d postgres

# To connect directly:
# psql -U xerxez_user -d xerxez_db -h localhost
