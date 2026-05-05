"""
Database Management Script
Smart PostgreSQL database management with soft coding
"""

import os
import sys
import subprocess
import psycopg2
from pathlib import Path

# Add config to path
sys.path.insert(0, os.path.join(Path(__file__).resolve().parent.parent, 'config'))
from backend_config import backend_config

class DatabaseManager:
    """
    PostgreSQL database management utility
    """
    
    def __init__(self):
        self.config = backend_config.get('database.default')
        self.db_url = backend_config.get_database_url()
        
    def get_connection_params(self):
        """Get connection parameters"""
        return {
            'host': self.config['host'],
            'port': self.config['port'],
            'user': self.config['user'],
            'password': self.config['password'],
            'database': self.config['name']
        }
    
    def test_connection(self):
        """Test database connection"""
        print("🔌 Testing database connection...")
        try:
            conn_params = self.get_connection_params()
            conn = psycopg2.connect(**conn_params)
            conn.close()
            print("✅ Database connection successful")
            return True
        except psycopg2.Error as e:
            print(f"❌ Database connection failed: {e}")
            return False
    
    def create_database(self):
        """Create database if it doesn't exist"""
        print(f"🏗️ Creating database '{self.config['name']}'...")
        
        try:
            # Connect to postgres database first
            conn_params = self.get_connection_params()
            conn_params['database'] = 'postgres'
            
            conn = psycopg2.connect(**conn_params)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Check if database exists
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.config['name'],))
            if cursor.fetchone():
                print(f"📝 Database '{self.config['name']}' already exists")
                return True
            
            # Create database
            cursor.execute(f"CREATE DATABASE {self.config['name']}")
            print(f"✅ Database '{self.config['name']}' created successfully")
            
            conn.close()
            return True
            
        except psycopg2.Error as e:
            print(f"❌ Failed to create database: {e}")
            return False
    
    def drop_database(self, confirm=True):
        """Drop database"""
        if confirm:
            response = input(f"⚠️ Are you sure you want to drop '{self.config['name']}'? (yes/no): ")
            if response.lower() != 'yes':
                print("❌ Operation cancelled")
                return False
        
        print(f"🗑️ Dropping database '{self.config['name']}'...")
        
        try:
            # Connect to postgres database
            conn_params = self.get_connection_params()
            conn_params['database'] = 'postgres'
            
            conn = psycopg2.connect(**conn_params)
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Terminate existing connections
            cursor.execute(f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{self.config['name']}' AND pid <> pg_backend_pid()
            """)\n            
            # Drop database
            cursor.execute(f"DROP DATABASE IF EXISTS {self.config['name']}")
            print(f"✅ Database '{self.config['name']}' dropped successfully")
            
            conn.close()
            return True
            
        except psycopg2.Error as e:
            print(f"❌ Failed to drop database: {e}")
            return False
    
    def backup_database(self, output_file=None):
        """Backup database using pg_dump"""
        if not output_file:
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"{self.config['name']}_backup_{timestamp}.sql"
        
        print(f"💾 Backing up database to {output_file}...")
        
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config['password']
            
            cmd = [
                'pg_dump',
                '-h', self.config['host'],
                '-p', str(self.config['port']),
                '-U', self.config['user'],
                '-d', self.config['name'],
                '-f', output_file,
                '--verbose'
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Database backed up to {output_file}")
                return True
            else:
                print(f"❌ Backup failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            print("❌ pg_dump not found. Please ensure PostgreSQL tools are installed.")
            return False
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False
    
    def restore_database(self, backup_file):
        """Restore database from backup"""
        print(f"🔄 Restoring database from {backup_file}...")
        
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config['password']
            
            cmd = [
                'psql',
                '-h', self.config['host'],
                '-p', str(self.config['port']),
                '-U', self.config['user'],
                '-d', self.config['name'],
                '-f', backup_file,
                '--verbose'
            ]
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Database restored from {backup_file}")
                return True
            else:
                print(f"❌ Restore failed: {result.stderr}")
                return False
                
        except FileNotFoundError:
            print("❌ psql not found. Please ensure PostgreSQL tools are installed.")
            return False
        except Exception as e:
            print(f"❌ Restore failed: {e}")
            return False
    
    def get_database_info(self):
        """Get database information"""
        print("📊 Database Information:")
        print(f"Host: {self.config['host']}")
        print(f"Port: {self.config['port']}")
        print(f"Database: {self.config['name']}")
        print(f"User: {self.config['user']}")
        
        try:
            conn = psycopg2.connect(**self.get_connection_params())
            cursor = conn.cursor()
            
            # Get database size
            cursor.execute(f"""
                SELECT pg_size_pretty(pg_database_size('{self.config['name']}'))
            """)
            size = cursor.fetchone()[0]
            print(f"Size: {size}")
            
            # Get table count
            cursor.execute("""
                SELECT count(*) FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_count = cursor.fetchone()[0]
            print(f"Tables: {table_count}")
            
            conn.close()
            
        except psycopg2.Error as e:
            print(f"❌ Could not get database info: {e}")

if __name__ == '__main__':
    manager = DatabaseManager()
    
    if len(sys.argv) < 2:
        print("""
🗄️ Database Management Script

Available commands:
  test        - Test database connection
  create      - Create database
  drop        - Drop database
  backup [file] - Backup database  
  restore <file> - Restore from backup
  info        - Show database information
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    try:
        if command == 'test':
            manager.test_connection()
        elif command == 'create':
            manager.create_database()
        elif command == 'drop':
            manager.drop_database()
        elif command == 'backup':
            output_file = args[0] if args else None
            manager.backup_database(output_file)
        elif command == 'restore':
            if not args:
                print("❌ Please specify a backup file")
                sys.exit(1)
            manager.restore_database(args[0])
        elif command == 'info':
            manager.get_database_info()
        else:
            print(f"❌ Unknown command: {command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)