import paramiko
import time
import sys

host = '192.168.11.208'
user = 'nikita'
password = '13081996'

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    print(f"Connecting to {host}...")
    ssh.connect(host, username=user, password=password, timeout=10)
    print("Connected.")
    
    # 1. Find the project folder
    stdin, stdout, stderr = ssh.exec_command("find /home /var/www /opt -maxdepth 3 -type d -name 'fitness_studio*' -exec test -e '{}/docker-compose.yml' \\; -print 2>/dev/null | head -n 1")
    project_dir = stdout.read().decode('utf-8').strip()
    
    if not project_dir:
        print("Could not find project directory 'fitness_studio_mono' in home directory.")
        sys.exit(1)
        
    print(f"Project found at: {project_dir}")
    
    # 2. Run git pull
    print("Running git pull...")
    stdin, stdout, stderr = ssh.exec_command(f"cd {project_dir} && git stash && git pull")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))
    
    # 3. Run database migrations to add missing columns to server DB so data is kept
    print("Running database migrations on server...")
    migration_script = """
import sqlite3
import sys

try:
    conn = sqlite3.connect('database/planner.db')
    
    # admin_users
    try: conn.execute("ALTER TABLE admin_users ADD COLUMN role VARCHAR DEFAULT 'trainer'")
    except Exception as e: pass
    
    try: conn.execute("ALTER TABLE admin_users ADD COLUMN is_active BOOLEAN DEFAULT 1")
    except Exception as e: pass
    
    # other tables trainer_id
    tables = ['appointments', 'clients', 'incomes', 'expenses', 'packages', 'push_subscriptions']
    for t in tables:
        try: conn.execute(f"ALTER TABLE {t} ADD COLUMN trainer_id INTEGER DEFAULT 1")
        except Exception as e: pass
        
    # Delete 0 incomes
    conn.execute("DELETE FROM incomes WHERE amount = 0")
    conn.execute("DELETE FROM expenses WHERE amount = 0")
    
    conn.commit()
    conn.close()
    print("Migration finished.")
except Exception as err:
    print("Fatal migration error:", err)
"""
    # Create the migration script file on server
    stdin, stdout, stderr = ssh.exec_command(f"cat > {project_dir}/migrate.py")
    stdin.write(migration_script)
    stdin.close()
    
    # Run the python script with sudo
    stdin, stdout, stderr = ssh.exec_command(f"cd {project_dir} && echo {password} | sudo -S python3 migrate.py")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))
    
    # Remove the migration script
    ssh.exec_command(f"rm {project_dir}/migrate.py")
    
    # 4. Restart docker containers
    print("Restarting docker...")
    stdin, stdout, stderr = ssh.exec_command(f"cd {project_dir} && echo {password} | sudo -S docker compose down && echo {password} | sudo -S docker compose build && echo {password} | sudo -S docker compose up -d")
    print(stdout.read().decode('utf-8'))
    print(stderr.read().decode('utf-8'))
    
    print("Deployment successful.")
finally:
    ssh.close()
