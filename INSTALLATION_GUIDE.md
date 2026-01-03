# Vanna 2.0 - VM Installation Guide

Complete guide for deploying Vanna 2.0 Text-to-SQL application on a Virtual Machine using Docker.

## Table of Contents

- [Prerequisites](#prerequisites)
- [VM Setup](#vm-setup)
- [Installation Steps](#installation-steps)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Loading Training Data](#loading-training-data)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Prerequisites

### VM Requirements

- **OS**: Ubuntu 20.04 LTS or later (recommended) / CentOS 7+ / Debian 11+
- **CPU**: Minimum 2 cores (4 cores recommended)
- **RAM**: Minimum 4 GB (8 GB recommended)
- **Storage**: Minimum 20 GB free space
- **Network**: Open ports 8000, 8501, 5433

### Required Software

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git (for cloning repository)
- curl/wget (for testing)

---

## VM Setup

### 1. Connect to Your VM

```bash
# SSH into your VM
ssh username@your-vm-ip-address

# Or if using Azure VM with key-based auth
ssh -i ~/.ssh/your-key.pem azureuser@your-vm-ip
```

### 2. Update System Packages

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# CentOS/RHEL
sudo yum update -y
```

### 3. Install Docker Engine

#### Ubuntu/Debian

```bash
# Remove old versions
sudo apt remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verify installation
docker --version
```

#### CentOS/RHEL

```bash
# Install dependencies
sudo yum install -y yum-utils

# Add Docker repository
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# Install Docker Engine
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Verify installation
docker --version
```

### 4. Configure Docker Permissions

```bash
# Add current user to docker group
sudo usermod -aG docker $USER

# Apply group changes (or logout and login again)
newgrp docker

# Test Docker without sudo
docker run hello-world
```

### 5. Install Docker Compose (if not included)

```bash
# Check if docker compose is available
docker compose version

# If not available, install standalone version
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify
docker-compose --version
```

---

## Installation Steps

### 1. Clone or Transfer Project Files

#### Option A: Clone from Git Repository

```bash
# If your project is in a Git repository
cd ~
git clone https://your-repo-url/venna_test3.git
cd venna_test3
```

#### Option B: Transfer Files via SCP

```bash
# From your local machine
scp -r /path/to/venna_test3 username@vm-ip:/home/username/

# Then on VM
cd ~/venna_test3
```

#### Option C: Manual Upload

If you prefer, you can upload files via SFTP or other file transfer methods.

### 2. Verify Project Structure

```bash
# Check that all required files are present
ls -la

# Expected structure:
# venna_test3/
# ├── docker-compose.yml
# ├── Dockerfile
# ├── Dockerfile.ui
# ├── .env.example (or .env)
# ├── requirements.txt
# ├── src/
# ├── training_data/
# └── scripts/
```

---

## Configuration

### 1. Create Environment File

```bash
# If .env doesn't exist, copy from example
cp .env.example .env

# Or create new .env file
nano .env
```

### 2. Configure Environment Variables

Edit `.env` file with your actual credentials:

```bash
nano .env
```

**Required Configuration:**

```env
# ============================================
# Azure OpenAI Configuration
# ============================================
AZURE_OPENAI_API_KEY=your_azure_openai_api_key_here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_VERSION=2025-01-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5.1

# Embedding Model Configuration
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-ada-002
AZURE_OPENAI_EMBEDDINGS_API_VERSION=2023-05-15

# ============================================
# Data Source - AdventureWorksDW (PostgreSQL)
# ============================================
DATA_SOURCE_HOST=your-postgres-host.database.azure.com
DATA_SOURCE_PORT=5432
DATA_SOURCE_DB=AdventureWorksDW
DATA_SOURCE_USER=your_db_user
DATA_SOURCE_PASSWORD=your_db_password

# ============================================
# pgvector (Local Vector Store)
# ============================================
PGVECTOR_HOST=pgvector-db
PGVECTOR_PORT=5432
PGVECTOR_DB=vanna_vectors
PGVECTOR_USER=vanna
PGVECTOR_PASSWORD=vanna_secure_password_123

# ============================================
# Application Settings
# ============================================
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

**Important Notes:**
- Replace `your_azure_openai_api_key_here` with your actual Azure OpenAI API key
- Update `AZURE_OPENAI_ENDPOINT` with your Azure OpenAI endpoint URL
- Update `DATA_SOURCE_HOST`, `DATA_SOURCE_USER`, and `DATA_SOURCE_PASSWORD` with your PostgreSQL credentials
- Keep `PGVECTOR_HOST=pgvector-db` (this is the Docker container name)

### 3. Secure the Environment File

```bash
# Set proper permissions
chmod 600 .env

# Verify permissions
ls -la .env
```

### 4. Configure Firewall (if needed)

```bash
# Ubuntu/Debian (using ufw)
sudo ufw allow 8000/tcp
sudo ufw allow 8501/tcp
sudo ufw allow 5433/tcp
sudo ufw reload

# CentOS/RHEL (using firewalld)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --permanent --add-port=5433/tcp
sudo firewall-cmd --reload
```

### 5. Configure Cloud Provider Network Security (if applicable)

#### Azure VM

```bash
# Allow inbound ports in Azure Network Security Group (NSG)
# Go to Azure Portal > Virtual Machines > Your VM > Networking
# Add inbound port rules:
# - Port 8000 (FastAPI Backend)
# - Port 8501 (Web UI)
# - Port 5433 (pgvector - optional, for external access)
```

#### AWS EC2

```bash
# Allow inbound ports in Security Group
# Go to EC2 Console > Security Groups > Your SG
# Add inbound rules:
# - Custom TCP Rule: Port 8000, Source: 0.0.0.0/0
# - Custom TCP Rule: Port 8501, Source: 0.0.0.0/0
# - Custom TCP Rule: Port 5433, Source: 0.0.0.0/0 (optional)
```

---

## Deployment

### 1. Build and Start Services

```bash
# Build Docker images and start all services
docker compose up -d --build

# View logs during startup
docker compose logs -f
```

**Expected Output:**
```
[+] Running 4/4
 ✔ Network vanna-network        Created
 ✔ Volume "venna_test3_pgvector_data"  Created
 ✔ Container pgvector-db        Started
 ✔ Container vanna-app          Started
 ✔ Container vanna-ui           Started
```

### 2. Monitor Service Status

```bash
# Check running containers
docker compose ps

# Expected output:
# NAME          IMAGE                         STATUS         PORTS
# pgvector-db   pgvector/pgvector:0.8.0-pg16  Up (healthy)   0.0.0.0:5433->5432/tcp
# vanna-app     venna_test3-vanna-app         Up             0.0.0.0:8000->8000/tcp
# vanna-ui      venna_test3-vanna-ui          Up             0.0.0.0:8501->8501/tcp
```

### 3. View Service Logs

```bash
# View all logs
docker compose logs

# View specific service logs
docker compose logs vanna-app
docker compose logs pgvector-db
docker compose logs vanna-ui

# Follow logs in real-time
docker compose logs -f vanna-app
```

### 4. Verify Container Health

```bash
# Check pgvector health
docker inspect pgvector-db --format='{{.State.Health.Status}}'
# Should return: healthy

# Check if all containers are running
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
```

---

## Loading Training Data

### 1. Verify Training Data Files

```bash
# Check training data directory
ls -la training_data/

# Expected files:
# - ddl.json
# - documentation.json
# - sql_examples.json
```

### 2. Load Training Data into pgvector

```bash
# Execute the training data loader script
docker exec -it vanna-app python scripts/load_training_data.py
```

**Expected Output:**
```
Loading training data into pgvector...
✓ Loaded 5 DDL statements
✓ Loaded 5 documentation entries
✓ Loaded 8 SQL examples
Training data loaded successfully!
```

### 3. Verify Data Was Loaded

```bash
# Connect to pgvector database
docker exec -it pgvector-db psql -U vanna -d vanna_vectors

# Run queries to verify data
SELECT COUNT(*) FROM vanna_ddl;
SELECT COUNT(*) FROM vanna_documentation;
SELECT COUNT(*) FROM vanna_sql_examples;

# Exit psql
\q
```

**Alternative: Load Data from SQL Dump (if provided)**

```bash
# If you have a SQL dump file
docker exec -i pgvector-db psql -U vanna -d vanna_vectors < training_data_backup.sql
```

---

## Verification

### 1. Test Backend API

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","message":"Vanna Text-to-SQL API is running"}

# Test root endpoint
curl http://localhost:8000/

# List available tables
curl http://localhost:8000/api/tables

# Test query endpoint
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total revenue?"}'
```

### 2. Access Web UI

Open your browser and navigate to:

```
http://your-vm-ip:8501
```

**Or test from command line:**

```bash
curl -I http://localhost:8501
# Should return: HTTP/1.1 200 OK
```

### 3. Test from External Network

```bash
# From your local machine
curl http://your-vm-public-ip:8000/health
curl -I http://your-vm-public-ip:8501
```

### 4. Test End-to-End Functionality

1. Open browser: `http://your-vm-ip:8501`
2. Enter a question: "What is the total revenue?"
3. Verify SQL is generated
4. Verify results are displayed

---

## Troubleshooting

### Common Issues

#### 1. Containers Not Starting

```bash
# Check container logs
docker compose logs vanna-app
docker compose logs pgvector-db

# Common issues:
# - Port already in use
# - Environment variables not set
# - Database connection failed
```

#### 2. Connection Refused Errors

```bash
# Verify ports are open
sudo netstat -tlnp | grep -E '8000|8501|5433'

# Check firewall
sudo ufw status

# Verify containers are running
docker compose ps
```

#### 3. pgvector Not Healthy

```bash
# Check pgvector logs
docker compose logs pgvector-db

# Restart pgvector
docker compose restart pgvector-db

# Check health manually
docker exec pgvector-db pg_isready -U vanna -d vanna_vectors
```

#### 4. Azure OpenAI Connection Errors

```bash
# Test Azure OpenAI connectivity from container
docker exec -it vanna-app python -c "
import os
from openai import AzureOpenAI
client = AzureOpenAI(
    api_key=os.getenv('AZURE_OPENAI_API_KEY'),
    api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
    azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
)
print('Connection successful!')
"
```

#### 5. Data Source Connection Failed

```bash
# Test PostgreSQL connection from container
docker exec -it vanna-app python -c "
import psycopg2
import os
conn = psycopg2.connect(
    host=os.getenv('DATA_SOURCE_HOST'),
    port=os.getenv('DATA_SOURCE_PORT'),
    database=os.getenv('DATA_SOURCE_DB'),
    user=os.getenv('DATA_SOURCE_USER'),
    password=os.getenv('DATA_SOURCE_PASSWORD')
)
print('Connection successful!')
conn.close()
"
```

#### 6. Training Data Not Loading

```bash
# Check if training data files exist
docker exec -it vanna-app ls -la /app/training_data/

# Check file permissions
docker exec -it vanna-app cat /app/training_data/ddl.json

# Re-run loader with verbose output
docker exec -it vanna-app python -u scripts/load_training_data.py
```

### Reset and Rebuild

```bash
# Stop all services
docker compose down

# Remove volumes (WARNING: This deletes all data)
docker compose down -v

# Rebuild and restart
docker compose up -d --build

# Reload training data
docker exec -it vanna-app python scripts/load_training_data.py
```

---

## Maintenance

### Starting and Stopping Services

```bash
# Stop all services
docker compose stop

# Start all services
docker compose start

# Restart all services
docker compose restart

# Stop and remove containers (keeps volumes)
docker compose down

# Stop and remove everything including volumes
docker compose down -v
```

### Viewing Logs

```bash
# View all logs
docker compose logs

# View logs for specific service
docker compose logs vanna-app

# Follow logs in real-time
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# View logs with timestamps
docker compose logs -t
```

### Updating the Application

```bash
# Pull latest code (if using git)
git pull origin main

# Rebuild and restart
docker compose up -d --build

# Reload training data if schema changed
docker exec -it vanna-app python scripts/load_training_data.py
```

### Backing Up Data

```bash
# Backup pgvector database
docker exec pgvector-db pg_dump -U vanna vanna_vectors > pgvector_backup_$(date +%Y%m%d).sql

# Backup environment file
cp .env .env.backup.$(date +%Y%m%d)

# Backup training data
tar -czf training_data_backup_$(date +%Y%m%d).tar.gz training_data/
```

### Restoring Data

```bash
# Restore pgvector database
docker exec -i pgvector-db psql -U vanna -d vanna_vectors < pgvector_backup_20250127.sql

# Or reload from training data
docker exec -it vanna-app python scripts/load_training_data.py
```

### Monitoring Resource Usage

```bash
# View resource usage
docker stats

# View disk usage
docker system df

# Clean up unused resources
docker system prune -a --volumes
```

### Checking Application Health

```bash
# Create a health check script
cat > health_check.sh << 'EOF'
#!/bin/bash
echo "=== Docker Container Status ==="
docker compose ps

echo -e "\n=== API Health Check ==="
curl -s http://localhost:8000/health | jq '.'

echo -e "\n=== UI Health Check ==="
curl -I -s http://localhost:8501 | head -n 1

echo -e "\n=== pgvector Status ==="
docker exec pgvector-db pg_isready -U vanna -d vanna_vectors
EOF

chmod +x health_check.sh
./health_check.sh
```

### Setting Up Auto-Start on Boot

```bash
# Enable Docker to start on boot
sudo systemctl enable docker

# Services will auto-start because of restart policies in docker-compose.yml
# Verify restart policy
docker inspect vanna-app --format='{{.HostConfig.RestartPolicy.Name}}'
```

### Viewing Container Resource Limits

```bash
# Check container resource usage
docker stats --no-stream

# Inspect specific container
docker inspect vanna-app | grep -A 10 "Memory\|Cpu"
```

---

## Quick Reference Commands

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f vanna-app

# Load training data
docker exec -it vanna-app python scripts/load_training_data.py

# Health check
curl http://localhost:8000/health

# Access UI
http://your-vm-ip:8501

# Restart specific service
docker compose restart vanna-app

# Execute commands in container
docker exec -it vanna-app bash

# View container resource usage
docker stats
```

---

## Security Recommendations

1. **Environment Variables**: Never commit `.env` to version control
2. **Firewall**: Only open necessary ports
3. **SSL/TLS**: Consider adding reverse proxy (nginx) with SSL certificates
4. **Database Passwords**: Use strong passwords for pgvector
5. **API Keys**: Rotate Azure OpenAI keys regularly
6. **Updates**: Keep Docker and base images updated
7. **Backups**: Schedule regular backups of pgvector data

---

## Support and Documentation

- **Project README**: See `README.md` for application overview
- **UI Documentation**: See `UI_README.md` for UI features
- **Architecture**: See `architecture.drawio` for system design
- **Docker Documentation**: https://docs.docker.com/
- **Docker Compose**: https://docs.docker.com/compose/

---

## License

MIT License

---

**Installation completed!** Your Vanna 2.0 Text-to-SQL application should now be running on your VM.

Access the Web UI at: `http://your-vm-ip:8501`
