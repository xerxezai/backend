"""
XERXEZ Backend Setup Script
Automated setup for Django backend with soft coding
"""

import os
import sys
import subprocess
from pathlib import Path
import shutil

class BackendSetup:
    """
    Automated backend setup utility
    """
    
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.venv_path = self.base_dir / 'venv'
        
    def print_step(self, step, message):
        """Print formatted step message"""
        print(f"\n{'='*60}")
        print(f"📋 STEP {step}: {message}")
        print(f"{'='*60}")
    
    def run_command(self, command, cwd=None, check=True):
        """Run shell command"""
        print(f"🚀 Running: {command}")
        result = subprocess.run(command, shell=True, cwd=cwd or self.base_dir)
        if check and result.returncode != 0:
            print(f"❌ Command failed: {command}")
            sys.exit(1)
        return result.returncode == 0
    
    def check_python(self):
        """Check Python version"""
        print("🐍 Checking Python version...")
        version = sys.version_info
        if version < (3, 9):
            print("❌ Python 3.9+ is required")
            sys.exit(1)
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} detected")
    
    def setup_virtual_environment(self):
        """Setup Python virtual environment"""
        self.print_step(1, "Setting Up Virtual Environment")
        
        if self.venv_path.exists():
            print("📁 Virtual environment already exists")
            return
        
        self.run_command(f"python -m venv {self.venv_path}")
        print("✅ Virtual environment created")
    
    def install_dependencies(self):
        """Install Python dependencies"""
        self.print_step(2, "Installing Dependencies")
        
        # Determine pip path based on OS
        if os.name == 'nt':  # Windows
            pip_path = self.venv_path / 'Scripts' / 'pip'
            python_path = self.venv_path / 'Scripts' / 'python'
        else:  # Unix-like
            pip_path = self.venv_path / 'bin' / 'pip'
            python_path = self.venv_path / 'bin' / 'python'
        
        # Install requirements
        requirements_file = self.base_dir / 'requirements' / 'dev.txt'
        self.run_command(f'"{pip_path}" install --upgrade pip')
        self.run_command(f'"{pip_path}" install -r "{requirements_file}"')
        print("✅ Dependencies installed")
    
    def setup_environment(self):
        """Setup environment configuration"""
        self.print_step(3, "Setting Up Environment")
        
        env_file = self.base_dir / '.env'
        env_template = self.base_dir / '.env.template'
        
        if not env_file.exists():
            if env_template.exists():
                shutil.copy(env_template, env_file)
                print("✅ Environment file created from template")
            else:
                print("❌ Environment template not found")
                return False
        else:
            print("📁 Environment file already exists")
        
        return True
    
    def setup_database(self):
        """Setup database"""
        self.print_step(4, "Setting Up Database")
        
        # Check if using SQLite (default for development)
        env_file = self.base_dir / '.env'
        use_sqlite = True
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                content = f.read()
                if 'USE_SQLITE=False' in content:
                    use_sqlite = False
        
        if use_sqlite:
            print("📝 Using SQLite for development (no setup required)")
        else:
            print("🗄️ PostgreSQL configuration detected")
            print("ℹ️ Make sure PostgreSQL is running and accessible")
            
            # Test database connection
            try:
                from scripts.db_manager import DatabaseManager
                db_manager = DatabaseManager()
                if db_manager.test_connection():
                    print("✅ Database connection successful")
                else:
                    print("❌ Database connection failed")
                    print("🔧 Please check your PostgreSQL configuration")
                    return False
            except Exception as e:
                print(f"⚠️ Could not test database connection: {e}")
    
    def run_migrations(self):
        """Run Django migrations"""
        self.print_step(5, "Running Database Migrations")
        
        manage_py = self.base_dir / 'manage.py'
        
        # Determine python path
        if os.name == 'nt':  # Windows
            python_path = self.venv_path / 'Scripts' / 'python'
        else:  # Unix-like
            python_path = self.venv_path / 'bin' / 'python'
        
        # Run migrations
        self.run_command(f'"{python_path}" "{manage_py}" makemigrations')
        self.run_command(f'"{python_path}" "{manage_py}" migrate')
        print("✅ Database migrations completed")
    
    def collect_static_files(self):
        """Collect static files"""
        self.print_step(6, "Collecting Static Files")
        
        manage_py = self.base_dir / 'manage.py'
        
        if os.name == 'nt':  # Windows
            python_path = self.venv_path / 'Scripts' / 'python'
        else:  # Unix-like
            python_path = self.venv_path / 'bin' / 'python'
        
        self.run_command(f'"{python_path}" "{manage_py}" collectstatic --noinput', check=False)
        print("✅ Static files collected")
    
    def create_superuser_prompt(self):
        """Prompt to create superuser"""
        self.print_step(7, "Create Admin User")
        
        response = input("🤔 Would you like to create an admin user? (y/n): ").lower()
        if response in ['y', 'yes']:
            manage_py = self.base_dir / 'manage.py'
            
            if os.name == 'nt':  # Windows
                python_path = self.venv_path / 'Scripts' / 'python'
            else:  # Unix-like
                python_path = self.venv_path / 'bin' / 'python'
            
            self.run_command(f'"{python_path}" "{manage_py}" createsuperuser')
            print("✅ Admin user created")
        else:
            print("ℹ️ Skipping admin user creation")
            print("💡 You can create one later with: npm run createsuperuser")
    
    def show_completion_info(self):
        """Show setup completion information"""
        self.print_step("COMPLETE", "Backend Setup Finished!")
        
        print("""
🎉 XERXEZ Backend is ready for development!

📋 Next Steps:
   1. Activate virtual environment:
      • Windows: venv\\Scripts\\activate
      • Unix/Mac: source venv/bin/activate
   
   2. Start development server:
      npm run dev
      OR
      python scripts/django_manager.py runserver
   
   3. Access your backend:
      • API Root: http://127.0.0.1:8000/
      • Admin Panel: http://127.0.0.1:8000/admin/
      • API Docs: http://127.0.0.1:8000/docs/
      • Health Check: http://127.0.0.1:8000/health/

🔧 Useful Commands:
   • npm run test          - Run tests
   • npm run shell         - Django shell
   • npm run migrate       - Run migrations
   • npm run db:info       - Database info
   • npm run format        - Format code
   
📚 Documentation:
   • README.md             - Complete documentation
   • /docs/                - API documentation
   
🎯 Frontend Integration:
   • CORS configured for: http://localhost:5173
   • API available at: http://127.0.0.1:8000/api/v1/
        """)
    
    def setup(self):
        """Run complete setup process"""
        print("""
🚀 XERXEZ Backend Setup
Setting up Django backend with soft coding architecture
        """)
        
        try:
            self.check_python()
            self.setup_virtual_environment()
            self.install_dependencies()
            self.setup_environment()
            self.setup_database()
            self.run_migrations()
            self.collect_static_files()
            self.create_superuser_prompt()
            self.show_completion_info()
            
        except KeyboardInterrupt:
            print("\n👋 Setup cancelled by user")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ Setup failed: {e}")
            sys.exit(1)

if __name__ == '__main__':
    setup = BackendSetup()
    setup.setup()