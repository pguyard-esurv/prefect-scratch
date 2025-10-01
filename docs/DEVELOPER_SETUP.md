# Developer Setup Guide

Welcome to the Distributed Processing RPA Project! This guide will help you set up the complete development environment from scratch.

## Quick Start

**For the impatient developer:**

```bash
# Clone the repository and navigate to it
git clone <repository-url>
cd prefect_scratch

# Run the automated setup script
./scripts/setup_dev_environment.sh

# Check that everything is working
./scripts/check_test_data.sh
```

That's it! Skip to the [What You Get](#what-you-get) section to see what was set up for you.

## Prerequisites

Before running the setup script, ensure you have:

- **Docker & Docker Compose**: [Install Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **uv** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Git**: For cloning the repository

## Setup Options

The setup script supports several options:

```bash
# Standard setup (recommended for first-time setup)
./scripts/setup_dev_environment.sh

# Clean setup (removes existing containers and data)
./scripts/setup_dev_environment.sh --clean

# Skip Docker image building (if images already exist)
./scripts/setup_dev_environment.sh --no-build

# Clean setup without rebuilding images
./scripts/setup_dev_environment.sh --clean --no-build

# Get help
./scripts/setup_dev_environment.sh --help
```

## What You Get

After running the setup script, you'll have:

### 🐳 **Container Services**
- **PostgreSQL Database** (localhost:5432)
  - `rpa_db` - Main application database with processing queue
  - `prefect_db` - Prefect server database
- **Prefect Server** (http://localhost:4200) - Workflow orchestration UI
- **3 RPA Worker Containers** - Distributed processing workers

### 📊 **Database Schema**
- `processing_queue` - Central queue for distributed task processing
- `customer_orders` - Sample customer order data
- `processed_surveys` - Sample survey processing results
- Complete with indexes, triggers, and sample data

### ⚙️ **Configuration**
- Container environment files for all services
- Proper networking between containers
- Health checks and resource limits
- Test data for immediate development

### 🧪 **Development Tools**
- Automated health checking
- Test data validation
- Container log monitoring
- Database connectivity testing

## Verifying Your Setup

Use the status checker to verify everything is working:

```bash
./scripts/check_test_data.sh
```

This will show you:
- Container health status
- Database connectivity
- Processing queue status
- Recent activity
- Live system test

## Common Development Tasks

### View Container Status
```bash
docker compose ps
```

### Check Worker Logs
```bash
# View logs for a specific worker
docker compose logs -f rpa1-worker

# View all logs
docker compose logs -f
```

### Access Database
```bash
# Connect to main application database
docker exec -it rpa-postgres psql -U rpa_user -d rpa_db

# Sample queries:
# SELECT * FROM processing_queue ORDER BY created_at DESC LIMIT 5;
# SELECT COUNT(*) FROM processing_queue WHERE status = 'pending';
```

### Access Prefect UI
Open http://localhost:4200 in your browser to:
- View flow runs
- Monitor worker activity
- Check flow deployments
- Access logs and metrics

### Test Distributed Processing
```sql
-- Insert a test record into the processing queue
INSERT INTO processing_queue (flow_name, payload, status) 
VALUES ('rpa1', '{"test": true, "customer_id": "DEV123"}', 'pending');

-- Watch it get processed by checking the status
SELECT * FROM processing_queue WHERE payload::text LIKE '%DEV123%';
```

### Restart Services
```bash
# Restart all workers
docker compose restart rpa1-worker rpa2-worker rpa3-worker

# Restart specific service
docker compose restart rpa1-worker

# Stop all services
docker compose down

# Start all services
docker compose up -d
```

## Development Workflow

1. **Make code changes** in your IDE
2. **Rebuild containers** (if needed):
   ```bash
   ./scripts/build_base_image.sh
   ./scripts/build_flow_images.sh --all
   ```
3. **Restart relevant workers**:
   ```bash
   docker compose restart rpa1-worker
   ```
4. **Test your changes**:
   ```bash
   ./scripts/check_test_data.sh
   ```

## Troubleshooting

### Containers Won't Start
```bash
# Check for port conflicts
docker compose down
./scripts/setup_dev_environment.sh --clean

# Check Docker resource limits
docker system df
docker system prune
```

### Database Connection Issues
```bash
# Check PostgreSQL health
docker compose logs postgres

# Test connectivity
docker exec rpa-postgres pg_isready -U rpa_user -d rpa_db
```

### Worker Health Check Failures
```bash
# Check worker logs
docker compose logs rpa1-worker

# Restart worker
docker compose restart rpa1-worker

# Rebuild and restart
./scripts/build_flow_images.sh rpa1
docker compose restart rpa1-worker
```

### Clean Slate Reset
```bash
# Nuclear option - completely reset everything
docker compose down --volumes
docker system prune -f
./scripts/setup_dev_environment.sh --clean
```

## Project Structure

```
prefect_scratch/
├── core/                          # Core application code
│   ├── docker/                   # Core container definitions
│   │   └── Dockerfile            # Base container image
│   ├── envs/.env.container       # Container environment config
│   ├── migrations/               # Database migration files
│   ├── database.py              # Database management
│   ├── distributed.py           # Distributed processing logic
│   └── config.py                # Configuration management
├── flows/                        # RPA workflow definitions
│   ├── rpa1/                    # RPA1 flow
│   │   ├── Dockerfile           # RPA1 container image
│   │   ├── .env.container       # RPA1 container config
│   │   └── workflow.py          # RPA1 workflow logic
│   ├── rpa2/                    # RPA2 flow
│   │   ├── Dockerfile           # RPA2 container image
│   │   ├── .env.container       # RPA2 container config
│   │   └── workflow.py          # RPA2 workflow logic
│   └── rpa3/                    # RPA3 flow
│       ├── Dockerfile           # RPA3 container image
│       ├── .env.container       # RPA3 container config
│       └── workflow.py          # RPA3 workflow logic
├── scripts/                     # Setup and utility scripts
│   ├── setup_dev_environment.sh # Main setup script
│   └── check_test_data.sh       # Status checker
├── docker-compose.yml           # Container orchestration
└── DEVELOPER_SETUP.md           # This file
```

## Environment Details

### Database Credentials
- **RPA Database**: `rpa_user` / `rpa_dev_password` @ `localhost:5432/rpa_db`
- **Prefect Database**: `prefect_user` / `prefect_dev_password` @ `localhost:5432/prefect_db`

### Service URLs
- **Prefect UI**: http://localhost:4200
- **Prefect API**: http://localhost:4200/api
- **PostgreSQL**: localhost:5432

### Container Network
- All containers communicate via `rpa-network`
- Database hostname: `postgres`
- Prefect hostname: `prefect-server`

## Need Help?

1. **Check the logs**: `docker compose logs -f`
2. **Run diagnostics**: `./scripts/check_test_data.sh`
3. **Reset everything**: `./scripts/setup_dev_environment.sh --clean`
4. **Read the script**: The setup script is well-commented and shows exactly what it does

## Contributing

When making changes:
1. Test with a clean setup: `./scripts/setup_dev_environment.sh --clean`
2. Update this documentation if you change setup requirements
3. Ensure the status checker script still passes
4. Update migration files for any schema changes

Happy coding! 🚀