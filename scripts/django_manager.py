"""
Django Management Script
Smart script for managing Django backend with soft coding
"""

import os
import sys
import subprocess
from pathlib import Path

class DjangoManager:
    """
    Smart Django management utility
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.manage_py = self.base_dir / 'manage.py'
        
    def run_command(self, command, *args, **kwargs):
        """Run Django management command"""
        cmd = [sys.executable, str(self.manage_py), command] + list(args)
        
        print(f"🚀 Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=self.base_dir, **kwargs)
        return result.returncode == 0
    
    def migrate(self, app=None):
        """Run database migrations"""
        print("📦 Running migrations...")
        args = [app] if app else []
        return self.run_command('migrate', *args)
    
    def makemigrations(self, app=None):
        """Create new migrations"""
        print("📝 Creating migrations...")
        args = [app] if app else []
        return self.run_command('makemigrations', *args)
    
    def collectstatic(self, no_input=True):
        """Collect static files"""
        print("📁 Collecting static files...")
        args = ['--noinput'] if no_input else []
        return self.run_command('collectstatic', *args)
    
    def createsuperuser(self):
        """Create superuser"""
        print("👤 Creating superuser...")
        return self.run_command('createsuperuser')
    
    def runserver(self, host='127.0.0.1', port='8000'):
        """Start development server"""
        print(f"🌐 Starting development server at {host}:{port}")
        return self.run_command('runserver', f'{host}:{port}')
    
    def shell(self):
        """Open Django shell"""
        print("🐍 Opening Django shell...")
        return self.run_command('shell')
    
    def test(self, app=None, verbose=True):
        """Run tests"""
        print("🧪 Running tests...")
        args = []
        if app:
            args.append(app)
        if verbose:
            args.append('--verbose')
        return self.run_command('test', *args)
    
    def loaddata(self, fixture):
        """Load data from fixture"""
        print(f"📊 Loading data from {fixture}...")
        return self.run_command('loaddata', fixture)
    
    def dumpdata(self, app, output_file=None):
        """Dump data to file"""
        print(f"💾 Dumping data from {app}...")
        args = [app, '--indent', '2']
        if output_file:
            args.extend(['--output', output_file])
        return self.run_command('dumpdata', *args)

if __name__ == '__main__':
    manager = DjangoManager()
    
    if len(sys.argv) < 2:
        print("""
🚀 Django Management Script

Available commands:
  migrate [app]           - Run migrations
  makemigrations [app]    - Create migrations  
  collectstatic          - Collect static files
  createsuperuser        - Create admin user
  runserver [host:port]  - Start dev server (default: 127.0.0.1:8000)
  shell                  - Open Django shell
  test [app]             - Run tests
  loaddata <fixture>     - Load fixture data
  dumpdata <app> [file]  - Dump app data
        """)
        sys.exit(1)
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    try:
        if command == 'migrate':
            manager.migrate(*args)
        elif command == 'makemigrations':
            manager.makemigrations(*args)
        elif command == 'collectstatic':
            manager.collectstatic()
        elif command == 'createsuperuser':
            manager.createsuperuser()
        elif command == 'runserver':
            host_port = args[0] if args else '127.0.0.1:8000'
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host, port = '127.0.0.1', host_port
            manager.runserver(host, port)
        elif command == 'shell':
            manager.shell()
        elif command == 'test':
            manager.test(*args)
        elif command == 'loaddata':
            if not args:
                print("❌ Please specify a fixture file")
                sys.exit(1)
            manager.loaddata(args[0])
        elif command == 'dumpdata':
            if not args:
                print("❌ Please specify an app name")
                sys.exit(1)
            output_file = args[1] if len(args) > 1 else None
            manager.dumpdata(args[0], output_file)
        else:
            print(f"❌ Unknown command: {command}")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)