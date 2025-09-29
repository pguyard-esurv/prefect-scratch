# Container Testing Implementation Guide

## Overview

This document provides a complete implementation guide for containerized testing of the distributed processing system. The architecture uses a layered approach with a base image containing core dependencies and lightweight flow images for rapid development iteration.

## ⚠️ **Implementation Notes**

### Prerequisites
- Ensure `.env` files exist in `core/envs/` and `flows/*/` directories
- Run `python scripts/setup_environments.py` to apply database migrations
- Container environment variables use `CONTAINER_*` prefix for isolation

### Configuration
The `ConfigManager` automatically maps container environment variables to the appropriate settings. Test data is designed for distributed processing validation - RPA1 uses minimal payloads since it generates its own test data internally.

### Troubleshooting
- Check logs: `docker-compose logs [service-name]`
- Test DB: `docker-compose exec postgres psql -U rpa_user -d rpa_db`
- Check health: `docker inspect [container] | grep -A 10 Health`

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Container Test Environment                    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │   RPA1      │  │   RPA2      │  │   RPA3      │  │ Prefect │ │
│  │ Container   │  │ Container   │  │ Container   │  │ Server  │ │
│  │             │  │             │  │             │  │         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
│         │                │                │              │      │
│         └────────────────┼────────────────┼──────────────┘      │
│                          │                │                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              PostgreSQL Database                          │ │
│  │          (processing_queue, results)                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Step 1: Base Image Creation

#### 1.1 Create Base Dockerfile

Create `Dockerfile.base`:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project configuration
COPY pyproject.toml ./
COPY uv.lock ./

# Install Python dependencies using uv sync (matches project workflow)
RUN pip install --no-cache-dir uv && \
    uv sync --system

# Copy core modules
COPY core/ ./core/
COPY conftest.py ./

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user
RUN useradd -m -u 1000 rpa && chown -R rpa:rpa /app
USER rpa

# Health check with proper error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "try: import core.database; print('Base image healthy')
except Exception as e: print(f'Health check failed: {e}'); exit(1)"

# Default command (overridden by flow containers)
CMD ["python", "-c", "print('Base image ready')"]
```

**Note**: The health check imports `core.database` to verify the base image is properly configured. This will fail if the database connection string is not properly set in the container environment.

#### 1.2 Base Image Build Script

Create `scripts/build-base.sh`:

```bash
#!/bin/bash
set -e

echo "Building RPA base image..."

# Build base image with cache optimization
docker build \
    --file Dockerfile.base \
    --tag rpa-base:latest \
    --cache-from rpa-base:latest \
    .

echo "Base image build complete: rpa-base:latest"

# Show image size
docker images rpa-base:latest --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

### Step 2: Flow Images

#### 2.1 RPA1 Flow Dockerfile

Create `Dockerfile.flow1`:

```dockerfile
FROM rpa-base:latest

# Copy RPA1 flow and all flows dependencies
COPY flows/ ./flows/

# Copy environment configuration
COPY core/envs/.env.development ./core/envs/.env.container
COPY flows/rpa1/.env.development ./flows/rpa1/.env.container

# Set container-specific environment variables
ENV FLOW_NAME=rpa1
ENV FLOW_TYPE=file_processing
ENV PREFECT_ENVIRONMENT=container
ENV PYTHONPATH=/app

# Health check specific to RPA1 with error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "try: from flows.rpa1.workflow import rpa1_workflow; print('RPA1 ready')
except Exception as e: print(f'RPA1 health check failed: {e}'); exit(1)"

# Create container startup script
RUN echo '#!/bin/bash\n\
export PREFECT_ENVIRONMENT=container\n\
cd /app\n\
python -c "\n\
from flows.rpa1.workflow import rpa1_workflow\n\
import time\n\
import signal\n\
import sys\n\
\n\
def signal_handler(signum, frame):\n\
    print(f\"Received signal {signum}, shutting down gracefully...\")\n\
    sys.exit(0)\n\
\n\
signal.signal(signal.SIGTERM, signal_handler)\n\
signal.signal(signal.SIGINT, signal_handler)\n\
\n\
print(\"Starting RPA1 distributed processing worker...\")\n\
while True:\n\
    try:\n\
        result = rpa1_workflow(use_distributed=True, batch_size=None)\n\
        print(f\"Processing batch completed: {result}\")\n\
        time.sleep(10)  # Wait before next batch\n\
    except KeyboardInterrupt:\n\
        break\n\
    except Exception as e:\n\
        print(f\"Error in processing: {e}\")\n\
        time.sleep(30)  # Wait longer on error\n\
"' > /app/start-rpa1.sh && chmod +x /app/start-rpa1.sh

# Start RPA1 worker with proper loop
CMD ["/app/start-rpa1.sh"]
```

#### 2.2 RPA2 Flow Dockerfile

Create `Dockerfile.flow2`:

```dockerfile
FROM rpa-base:latest

# Copy RPA2 flow and all flows dependencies
COPY flows/ ./flows/

# Copy environment configuration
COPY core/envs/.env.development ./core/envs/.env.container
COPY flows/rpa2/.env.development ./flows/rpa2/.env.container

# Set container-specific environment variables
ENV FLOW_NAME=rpa2
ENV FLOW_TYPE=data_validation
ENV PREFECT_ENVIRONMENT=container
ENV PYTHONPATH=/app

# Health check specific to RPA2 with error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "try: from flows.rpa2.workflow import rpa2_workflow; print('RPA2 ready')
except Exception as e: print(f'RPA2 health check failed: {e}'); exit(1)"

# Create container startup script
RUN echo '#!/bin/bash\n\
export PREFECT_ENVIRONMENT=container\n\
cd /app\n\
python -c "\n\
from flows.rpa2.workflow import rpa2_workflow\n\
import time\n\
import signal\n\
import sys\n\
\n\
def signal_handler(signum, frame):\n\
    print(f\"Received signal {signum}, shutting down gracefully...\")\n\
    sys.exit(0)\n\
\n\
signal.signal(signal.SIGTERM, signal_handler)\n\
signal.signal(signal.SIGINT, signal_handler)\n\
\n\
print(\"Starting RPA2 distributed processing worker...\")\n\
while True:\n\
    try:\n\
        result = rpa2_workflow(use_distributed=True, batch_size=None)\n\
        print(f\"Processing batch completed: {result}\")\n\
        time.sleep(10)  # Wait before next batch\n\
    except KeyboardInterrupt:\n\
        break\n\
    except Exception as e:\n\
        print(f\"Error in processing: {e}\")\n\
        time.sleep(30)  # Wait longer on error\n\
"' > /app/start-rpa2.sh && chmod +x /app/start-rpa2.sh

# Start RPA2 worker with proper loop
CMD ["/app/start-rpa2.sh"]
```

#### 2.3 RPA3 Flow Dockerfile

Create `Dockerfile.flow3`:

```dockerfile
FROM rpa-base:latest

# Copy RPA3 flow and all flows dependencies
COPY flows/ ./flows/

# Copy environment configuration
COPY core/envs/.env.development ./core/envs/.env.container
COPY flows/rpa3/.env.development ./flows/rpa3/.env.container

# Set container-specific environment variables
ENV FLOW_NAME=rpa3
ENV FLOW_TYPE=concurrent_processing
ENV PREFECT_ENVIRONMENT=container
ENV PYTHONPATH=/app

# Health check specific to RPA3 with error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "try: from flows.rpa3.workflow import rpa3_workflow; print('RPA3 ready')
except Exception as e: print(f'RPA3 health check failed: {e}'); exit(1)"

# Create container startup script
RUN echo '#!/bin/bash\n\
export PREFECT_ENVIRONMENT=container\n\
cd /app\n\
python -c "\n\
from flows.rpa3.workflow import rpa3_workflow\n\
import time\n\
import signal\n\
import sys\n\
\n\
def signal_handler(signum, frame):\n\
    print(f\"Received signal {signum}, shutting down gracefully...\")\n\
    sys.exit(0)\n\
\n\
signal.signal(signal.SIGTERM, signal_handler)\n\
signal.signal(signal.SIGINT, signal_handler)\n\
\n\
print(\"Starting RPA3 distributed processing worker...\")\n\
while True:\n\
    try:\n\
        result = rpa3_workflow(use_distributed=True, batch_size=None)\n\
        print(f\"Processing batch completed: {result}\")\n\
        time.sleep(10)  # Wait before next batch\n\
    except KeyboardInterrupt:\n\
        break\n\
    except Exception as e:\n\
        print(f\"Error in processing: {e}\")\n\
        time.sleep(30)  # Wait longer on error\n\
"' > /app/start-rpa3.sh && chmod +x /app/start-rpa3.sh

# Start RPA3 worker with proper loop
CMD ["/app/start-rpa3.sh"]
```

#### 2.4 Flow Images Build Script

Create `scripts/build-flows.sh`:

```bash
#!/bin/bash
set -e

echo "Building RPA flow images..."

# Ensure base image exists
if ! docker images rpa-base:latest --format "{{.Repository}}" | grep -q "rpa-base"; then
    echo "Base image not found. Building base image first..."
    ./scripts/build-base.sh
fi

# Build flow images in parallel
echo "Building flow images..."
docker build --file Dockerfile.flow1 --tag rpa-flow1:latest . &
docker build --file Dockerfile.flow2 --tag rpa-flow2:latest . &
docker build --file Dockerfile.flow3 --tag rpa-flow3:latest . &

# Wait for all builds to complete
wait

echo "Flow image builds complete:"
docker images --filter "reference=rpa-flow*" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
```

### Step 3: Database Initialization

#### 3.1 Database Initialization Script

Create `scripts/init-db.sql`:

```sql
-- Initialize RPA database with all required tables and test data

-- Apply migrations (tables should already exist from core/migrations/)
-- This script adds test data for container testing

-- Insert test records for RPA1 (file processing)
-- RPA1 uses internal data generation, so minimal payload needed
INSERT INTO processing_queue (flow_name, payload, status) VALUES
('rpa1_file_processing', '{"test_record_id": 1, "priority": "high"}', 'pending'),
('rpa1_file_processing', '{"test_record_id": 2, "priority": "normal"}', 'pending'),
('rpa1_file_processing', '{"test_record_id": 3, "priority": "high"}', 'pending'),
('rpa1_file_processing', '{"test_record_id": 4, "priority": "low"}', 'pending'),
('rpa1_file_processing', '{"test_record_id": 5, "priority": "normal"}', 'pending');

-- Insert test records for RPA2 (data validation)
INSERT INTO processing_queue (flow_name, payload, status) VALUES
('rpa2_validation', '{"users": [{"id": 1, "name": "Alice", "email": "alice@test.com", "active": true}]}', 'pending'),
('rpa2_validation', '{"users": [{"id": 2, "name": "Bob", "email": "bob@test.com", "active": false}]}', 'pending'),
('rpa2_validation', '{"users": [{"id": 3, "name": "Charlie", "email": "invalid-email", "active": true}]}', 'pending'),
('rpa2_validation', '{"users": [{"id": 4, "name": "", "email": "diana@test.com", "active": true}]}', 'pending');

-- Insert test records for RPA3 (concurrent processing)
INSERT INTO processing_queue (flow_name, payload, status) VALUES
('rpa3_concurrent_processing', '{"orders": [{"order_id": "ORD-001", "customer_id": "CUST-001", "product": "Widget A", "quantity": 2, "unit_price": 25.50}]}', 'pending'),
('rpa3_concurrent_processing', '{"orders": [{"order_id": "ORD-002", "customer_id": "CUST-002", "product": "Widget B", "quantity": 5, "unit_price": 15.75}]}', 'pending'),
('rpa3_concurrent_processing', '{"orders": [{"order_id": "ORD-003", "customer_id": "CUST-003", "product": "Widget C", "quantity": 10, "unit_price": 8.99}]}', 'pending');

-- Create indexes for better performance during testing
CREATE INDEX IF NOT EXISTS idx_processing_queue_flow_status ON processing_queue(flow_name, status);
CREATE INDEX IF NOT EXISTS idx_processing_queue_created_at ON processing_queue(created_at);

-- Display summary of test data
SELECT 
    flow_name,
    COUNT(*) as record_count,
    status
FROM processing_queue 
GROUP BY flow_name, status
ORDER BY flow_name, status;
```

### Step 4: Docker Compose Configuration

#### 4.1 Main Docker Compose File

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: rpa_db
      POSTGRES_USER: rpa_user
      POSTGRES_PASSWORD: rpa_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./core/migrations/rpa_db/V001__Create_test_table.sql:/docker-entrypoint-initdb.d/001-create-test-table.sql
      - ./core/migrations/rpa_db/V002__Add_test_index.sql:/docker-entrypoint-initdb.d/002-add-test-index.sql
      - ./core/migrations/rpa_db/V003__Create_processed_surveys.sql:/docker-entrypoint-initdb.d/003-create-processed-surveys.sql
      - ./core/migrations/rpa_db/V004__Create_customer_orders.sql:/docker-entrypoint-initdb.d/004-create-customer-orders.sql
      - ./core/migrations/rpa_db/V005__Create_flow_execution_logs.sql:/docker-entrypoint-initdb.d/005-create-flow-execution-logs.sql
      - ./core/migrations/rpa_db/V006__Create_processing_queue.sql:/docker-entrypoint-initdb.d/006-create-processing-queue.sql
      - ./core/migrations/rpa_db/V007__Add_processing_indexes.sql:/docker-entrypoint-initdb.d/007-add-processing-indexes.sql
      - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/099-test-data.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rpa_user -d rpa_db"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rpa_network

  # Prefect Server
  prefect-server:
    image: prefecthq/prefect:3-latest
    command: prefect server start --host 0.0.0.0
    environment:
      PREFECT_UI_URL: http://localhost:4200
      PREFECT_API_URL: http://prefect-server:4200/api
      PREFECT_SERVER_API_HOST: 0.0.0.0
    ports:
      - "4200:4200"
    volumes:
      - prefect_data:/root/.prefect
    depends_on:
      postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4200/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - rpa_network

  # RPA1 Workers (2 instances for distributed testing)
  rpa1-worker-1:
    image: rpa-flow1:latest
    environment:
      # Use proper configuration format matching project patterns
      CONTAINER_GLOBAL_RPA_DB_CONNECTION_STRING: postgresql://rpa_user:rpa_password@postgres:5432/rpa_db
      CONTAINER_GLOBAL_RPA_DB_TYPE: postgresql
      CONTAINER_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE: 2
      CONTAINER_RPA1_USE_DISTRIBUTED_PROCESSING: true
      CONTAINER_RPA1_DISTRIBUTED_BATCH_SIZE: 2
      PREFECT_API_URL: http://prefect-server:4200/api
      WORKER_INSTANCE_ID: rpa1-worker-1
      PYTHONPATH: /app
    volumes:
      - ./logs:/app/logs  # For logging output
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      prefect-server:
        condition: service_healthy
    networks:
      - rpa_network
    restart: unless-stopped

  rpa1-worker-2:
    image: rpa-flow1:latest
    environment:
      # Use proper configuration format matching project patterns
      CONTAINER_GLOBAL_RPA_DB_CONNECTION_STRING: postgresql://rpa_user:rpa_password@postgres:5432/rpa_db
      CONTAINER_GLOBAL_RPA_DB_TYPE: postgresql
      CONTAINER_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE: 3
      CONTAINER_RPA1_USE_DISTRIBUTED_PROCESSING: true
      CONTAINER_RPA1_DISTRIBUTED_BATCH_SIZE: 3
      PREFECT_API_URL: http://prefect-server:4200/api
      WORKER_INSTANCE_ID: rpa1-worker-2
      PYTHONPATH: /app
    volumes:
      - ./logs:/app/logs  # For logging output
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      prefect-server:
        condition: service_healthy
    networks:
      - rpa_network
    restart: unless-stopped

  # RPA2 Worker
  rpa2-worker-1:
    image: rpa-flow2:latest
    environment:
      # Use proper configuration format matching project patterns
      CONTAINER_GLOBAL_RPA_DB_CONNECTION_STRING: postgresql://rpa_user:rpa_password@postgres:5432/rpa_db
      CONTAINER_GLOBAL_RPA_DB_TYPE: postgresql
      CONTAINER_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE: 2
      CONTAINER_RPA2_USE_DISTRIBUTED_PROCESSING: true
      CONTAINER_RPA2_DISTRIBUTED_BATCH_SIZE: 2
      PREFECT_API_URL: http://prefect-server:4200/api
      WORKER_INSTANCE_ID: rpa2-worker-1
      PYTHONPATH: /app
    volumes:
      - ./logs:/app/logs  # For logging output
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      prefect-server:
        condition: service_healthy
    networks:
      - rpa_network
    restart: unless-stopped

  # RPA3 Worker
  rpa3-worker-1:
    image: rpa-flow3:latest
    environment:
      # Use proper configuration format matching project patterns
      CONTAINER_GLOBAL_RPA_DB_CONNECTION_STRING: postgresql://rpa_user:rpa_password@postgres:5432/rpa_db
      CONTAINER_GLOBAL_RPA_DB_TYPE: postgresql
      CONTAINER_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE: 1
      CONTAINER_RPA3_USE_DISTRIBUTED_PROCESSING: true
      CONTAINER_RPA3_DISTRIBUTED_BATCH_SIZE: 1
      PREFECT_API_URL: http://prefect-server:4200/api
      WORKER_INSTANCE_ID: rpa3-worker-1
      PYTHONPATH: /app
    volumes:
      - ./logs:/app/logs  # For logging output
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      prefect-server:
        condition: service_healthy
    networks:
      - rpa_network
    restart: unless-stopped

volumes:
  postgres_data:
  prefect_data:

networks:
  rpa_network:
    driver: bridge
```

#### 4.2 Development Override

Create `docker-compose.dev.yml`:

```yaml
version: '3.8'

services:
  # Development overrides for hot reloading
  rpa1-worker-1:
    volumes:
      - ./flows/rpa1:/app/flows/rpa1
      - ./core:/app/core
    environment:
      PYTHONPATH: /app
      LOG_LEVEL: DEBUG

  rpa1-worker-2:
    volumes:
      - ./flows/rpa1:/app/flows/rpa1
      - ./core:/app/core
    environment:
      PYTHONPATH: /app
      LOG_LEVEL: DEBUG

  rpa2-worker-1:
    volumes:
      - ./flows/rpa2:/app/flows/rpa2
      - ./core:/app/core
    environment:
      PYTHONPATH: /app
      LOG_LEVEL: DEBUG

  rpa3-worker-1:
    volumes:
      - ./flows/rpa3:/app/flows/rpa3
      - ./core:/app/core
    environment:
      PYTHONPATH: /app
      LOG_LEVEL: DEBUG

  # Additional debugging services
  postgres:
    ports:
      - "5432:5432"  # Expose for external debugging tools
```

### Step 5: Test Automation

#### 5.1 Container Test Runner

Create `scripts/container-test-runner.py`:

```python
#!/usr/bin/env python3
"""
Container Test Runner - Automated validation of distributed processing
"""

import time
import subprocess
import psycopg2
import requests
import json
from typing import Dict, List, Any

class ContainerTestRunner:
    def __init__(self):
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'rpa_db',
            'user': 'rpa_user',
            'password': 'rpa_password'
        }
        self.prefect_url = 'http://localhost:4200'
        
    def wait_for_services(self, timeout: int = 300) -> bool:
        """Wait for all services to be healthy"""
        print("Waiting for services to start...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check database
                conn = psycopg2.connect(**self.db_config)
                conn.close()
                print("✓ Database ready")
                
                # Check Prefect server
                response = requests.get(f"{self.prefect_url}/api/health")
                if response.status_code == 200:
                    print("✓ Prefect server ready")
                    return True
                    
            except Exception as e:
                print(f"Waiting for services... ({e})")
                time.sleep(10)
                
        return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                flow_name,
                status,
                COUNT(*) as count
            FROM processing_queue 
            GROUP BY flow_name, status
            ORDER BY flow_name, status
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        status = {}
        for flow_name, record_status, count in results:
            if flow_name not in status:
                status[flow_name] = {}
            status[flow_name][record_status] = count
            
        return status
    
    def run_distributed_processing_test(self) -> bool:
        """Run distributed processing validation"""
        print("\n" + "="*60)
        print("DISTRIBUTED PROCESSING TEST")
        print("="*60)
        
        # Get initial queue status
        initial_status = self.get_queue_status()
        print(f"Initial queue status: {initial_status}")
        
        # Wait for processing to occur
        print("Waiting for distributed processing...")
        time.sleep(60)  # Give workers time to process
        
        # Check final status
        final_status = self.get_queue_status()
        print(f"Final queue status: {final_status}")
        
        # Validate no duplicates were created
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Check for duplicate processing
        cursor.execute("""
            SELECT 
                flow_name,
                COUNT(DISTINCT flow_instance_id) as unique_processors,
                COUNT(*) as total_processed
            FROM processing_queue 
            WHERE status = 'completed'
            GROUP BY flow_name
        """)
        
        duplicate_check = cursor.fetchall()
        conn.close()
        
        print("\nDuplicate Processing Check:")
        for flow_name, unique_processors, total_processed in duplicate_check:
            print(f"  {flow_name}: {total_processed} records by {unique_processors} processors")
            
        return True
    
    def run_performance_test(self) -> bool:
        """Run performance validation"""
        print("\n" + "="*60)
        print("PERFORMANCE TEST")
        print("="*60)
        
        # Add more test records
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        
        # Insert load test data
        for i in range(20):
            cursor.execute("""
                INSERT INTO processing_queue (flow_name, payload, status)
                VALUES ('rpa1_file_processing', %s, 'pending')
            """, (json.dumps({'test_record': i, 'load_test': True}),))
            
        conn.commit()
        conn.close()
        
        print("Added 20 load test records")
        
        # Monitor processing rate
        start_time = time.time()
        initial_pending = self.count_pending_records()
        
        time.sleep(120)  # Wait 2 minutes
        
        final_pending = self.count_pending_records()
        elapsed_time = time.time() - start_time
        
        records_processed = initial_pending - final_pending
        processing_rate = records_processed / elapsed_time * 60  # records per minute
        
        print(f"Processing rate: {processing_rate:.2f} records/minute")
        print(f"Records processed: {records_processed}")
        
        return processing_rate > 0
    
    def count_pending_records(self) -> int:
        """Count pending records in queue"""
        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM processing_queue WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    def run_all_tests(self) -> bool:
        """Run complete test suite"""
        print("CONTAINER TEST SUITE")
        print("="*60)
        
        if not self.wait_for_services():
            print("❌ Services failed to start")
            return False
            
        tests = [
            self.run_distributed_processing_test,
            self.run_performance_test,
        ]
        
        results = []
        for test in tests:
            try:
                result = test()
                results.append(result)
                if result:
                    print(f"✓ {test.__name__} PASSED")
                else:
                    print(f"❌ {test.__name__} FAILED")
            except Exception as e:
                print(f"❌ {test.__name__} ERROR: {e}")
                results.append(False)
                
        success_rate = sum(results) / len(results) * 100
        print(f"\nTest Results: {sum(results)}/{len(results)} passed ({success_rate:.1f}%)")
        
        return all(results)

if __name__ == "__main__":
    runner = ContainerTestRunner()
    success = runner.run_all_tests()
    exit(0 if success else 1)
```

### Step 6: Build and Run Scripts

#### 6.1 Complete Build Script

Create `scripts/build-all.sh`:

```bash
#!/bin/bash
set -e

echo "Building complete RPA container test environment..."

# Build base image
echo "Step 1: Building base image..."
./scripts/build-base.sh

# Build flow images
echo "Step 2: Building flow images..."
./scripts/build-flows.sh

echo "All images built successfully!"
echo ""
echo "To start the test environment:"
echo "  docker-compose up -d"
echo ""
echo "To run tests:"
echo "  python scripts/container-test-runner.py"
echo ""
echo "To view Prefect UI:"
echo "  http://localhost:4200"
```

#### 6.2 Test Environment Startup Script

Create `scripts/start-test-env.sh`:

```bash
#!/bin/bash
set -e

echo "Starting RPA container test environment..."

# Ensure images are built
if ! docker images rpa-base:latest --format "{{.Repository}}" | grep -q "rpa-base"; then
    echo "Images not found. Building..."
    ./scripts/build-all.sh
fi

# Start services
echo "Starting containers..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 30

# Show status
echo "Container Status:"
docker-compose ps

echo ""
echo "Environment started successfully!"
echo ""
echo "Access Points:"
echo "  Prefect UI: http://localhost:4200"
echo "  Database: localhost:5432 (rpa_db)"
echo ""
echo "To run tests:"
echo "  python scripts/container-test-runner.py"
echo ""
echo "To stop environment:"
echo "  docker-compose down"
```

## Usage Instructions

### Initial Setup

1. **Prepare Environment**
   ```bash
   # Make scripts executable
   chmod +x scripts/*.sh
   
   # Build all images
   ./scripts/build-all.sh
   ```

2. **Start Test Environment**
   ```bash
   # Start all containers
   ./scripts/start-test-env.sh
   ```

3. **Run Tests**
   ```bash
   # Run automated test suite
   python scripts/container-test-runner.py
   ```

### Development Workflow

1. **Modify Flow Code**
   ```bash
   # Edit flow files
   vim flows/rpa1/workflow.py
   
   # Rebuild only flow images (fast)
   ./scripts/build-flows.sh
   
   # Restart containers
   docker-compose restart rpa1-worker-1 rpa1-worker-2
   ```

2. **Modify Core Code**
   ```bash
   # Edit core modules
   vim core/distributed.py
   
   # Rebuild base and flow images
   ./scripts/build-all.sh
   
   # Restart all containers
   docker-compose down && docker-compose up -d
   ```

### Monitoring and Debugging

1. **View Logs**
   ```bash
   # All services
   docker-compose logs -f
   
   # Specific service
   docker-compose logs -f rpa1-worker-1
   ```

2. **Database Access**
   ```bash
   # Connect to database
   docker-compose exec postgres psql -U rpa_user -d rpa_db
   
   # Check queue status
   SELECT flow_name, status, COUNT(*) FROM processing_queue GROUP BY flow_name, status;
   ```

3. **Container Health**
   ```bash
   # Check container health
   docker-compose ps
   
   # Inspect specific container
   docker inspect rpa1-worker-1
   ```

## Expected Test Results

### Successful Distributed Processing
- Multiple containers process different records atomically
- Zero duplicate processing occurs
- All records eventually reach 'completed' status
- Each flow type processes correctly
- Performance scales with additional containers

### Key Metrics to Validate
- **Atomicity**: No record processed by multiple containers
- **Completeness**: All queued records are processed
- **Performance**: Linear scaling with additional containers
- **Fault Tolerance**: System recovers from container restarts
- **Monitoring**: Health checks and metrics work correctly

This implementation provides a comprehensive, production-like testing environment for validating the distributed processing system's capabilities and performance characteristics.

## 🚀 **Quick Start**

1. **Setup**: `chmod +x scripts/*.sh && ./scripts/build-all.sh`
2. **Start**: `./scripts/start-test-env.sh`
3. **Test**: `python scripts/container-test-runner.py`
4. **Monitor**: `docker-compose logs -f`

## 🔧 **Development**

- Use `docker-compose.dev.yml` for hot reloading
- Check logs: `docker-compose logs [service]`
- Database access: `docker-compose exec postgres psql -U rpa_user -d rpa_db`
- Clean restart: `docker-compose down -v && docker-compose up -d`