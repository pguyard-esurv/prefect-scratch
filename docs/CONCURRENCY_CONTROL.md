# Concurrency Control in Prefect Workflows

This document explains how to control concurrency in Prefect workflows, with practical examples from our RPA solution.

## 🎯 Overview

Concurrency control is crucial for:
- **Resource Management**: Preventing system overload
- **Rate Limiting**: Respecting API limits
- **Performance Tuning**: Optimizing throughput vs resource usage
- **Cost Control**: Managing cloud compute costs

## 🔧 Methods of Concurrency Control

### 1. **Task Runner Level Concurrency**

The most common approach is to set concurrency at the flow level using `ConcurrentTaskRunner`:

```python
from prefect.task_runners import ConcurrentTaskRunner

@flow(
    name="my-workflow",
    task_runner=ConcurrentTaskRunner(max_workers=4),  # Limit to 4 concurrent tasks
    description="Workflow with controlled concurrency"
)
def my_workflow():
    # Your workflow code
```

**When to use**: When you want to limit the total number of concurrent tasks across your entire workflow.

### 2. **Task Level Concurrency**

Set concurrency limits on individual tasks:

```python
@task(concurrency_limit=2)  # Only 2 instances can run simultaneously
def api_call_task(data: dict) -> dict:
    # API call logic
    return result

@task(concurrency_limit=1)  # Only 1 instance can run at a time
def database_write_task(data: dict) -> dict:
    # Database write logic
    return result
```

**When to use**: When specific tasks have different concurrency requirements (e.g., API calls vs database writes).

### 3. **Configuration-Based Concurrency**

Use environment variables or Prefect's configuration system:

```python
from prefect import flow, get_run_logger
from core.config import ConfigManager

@flow(
    name="configurable-workflow",
    task_runner=ConcurrentTaskRunner(),  # Will be configured at runtime
    description="Workflow with configurable concurrency"
)
def configurable_workflow(max_workers: int = None):
    logger = get_run_logger()
    
    # Get concurrency from configuration
    config = ConfigManager("my_flow")
    max_concurrent = max_workers or config.get_variable("max_concurrent_tasks", 10)
    
    logger.info(f"Max concurrent tasks: {max_concurrent}")
    # Note: In practice, you'd need to recreate the task runner
    # with the new max_workers value
```

**When to use**: When you need different concurrency settings for different environments (dev/staging/prod).

## 📊 Concurrency Settings by Environment

Our RPA solution uses different concurrency settings for each environment:

### Development Environment
```python
# Low concurrency for development
Variable.set("development_rpa3_max_concurrent_tasks", "5")
Variable.set("development_rpa3_timeout", "30")
```

**Rationale**: 
- Lower resource usage
- Easier debugging
- Faster feedback loops

### Staging Environment
```python
# Medium concurrency for staging
Variable.set("staging_rpa3_max_concurrent_tasks", "8")
Variable.set("staging_rpa3_timeout", "60")
```

**Rationale**:
- Production-like performance testing
- Resource usage closer to production
- Validation of concurrency settings

### Production Environment
```python
# High concurrency for production
Variable.set("production_rpa3_max_concurrent_tasks", "15")
Variable.set("production_rpa3_timeout", "120")
```

**Rationale**:
- Maximum throughput
- Optimized for production workloads
- Higher resource allocation

## 🚀 Practical Examples

### Example 1: Basic Concurrency Control

```python
from prefect.task_runners import ConcurrentTaskRunner

@flow(
    name="basic-concurrent-workflow",
    task_runner=ConcurrentTaskRunner(max_workers=3)
)
def basic_concurrent_workflow():
    # Process 10 items with max 3 concurrent tasks
    items = list(range(10))
    results = process_item.map(items)  # Will process max 3 at a time
    return results
```

### Example 2: Task-Specific Concurrency

```python
@task(concurrency_limit=2)
def api_call_task(data: dict) -> dict:
    """API calls limited to 2 concurrent requests."""
    return call_external_api(data)

@task(concurrency_limit=1)
def database_write_task(data: dict) -> dict:
    """Database writes limited to 1 at a time."""
    return write_to_database(data)

@flow(
    name="mixed-concurrency-workflow",
    task_runner=ConcurrentTaskRunner(max_workers=5)
)
def mixed_concurrency_workflow():
    items = get_items()
    
    # API calls: max 2 concurrent
    api_results = api_call_task.map(items)
    
    # Database writes: max 1 concurrent
    db_results = database_write_task.map(api_results)
    
    return db_results
```

### Example 3: Dynamic Concurrency Based on Data Size

```python
@flow(
    name="dynamic-concurrency-workflow",
    task_runner=ConcurrentTaskRunner()
)
def dynamic_concurrency_workflow(data_size: int):
    logger = get_run_logger()
    
    # Adjust concurrency based on data size
    if data_size < 100:
        max_workers = 2
    elif data_size < 1000:
        max_workers = 5
    else:
        max_workers = 10
    
    logger.info(f"Processing {data_size} items with {max_workers} workers")
    
    # Note: In practice, you'd recreate the task runner here
    # This is a simplified example
    items = list(range(data_size))
    results = process_item.map(items)
    return results
```

## ⚡ Performance Considerations

### Choosing the Right Concurrency Level

1. **CPU-Bound Tasks**: Set concurrency to number of CPU cores
2. **I/O-Bound Tasks**: Can use higher concurrency (10-50+)
3. **API Calls**: Respect rate limits (usually 5-20)
4. **Database Operations**: Consider connection pool limits

### Monitoring Concurrency

```python
@task
def monitor_concurrency():
    """Monitor current concurrency usage."""
    logger = get_run_logger()
    
    # Get current task run context
    from prefect import get_run_context
    context = get_run_context()
    
    logger.info(f"Current concurrency: {context.task_run_count}")
    return context.task_run_count
```

## 🛠️ Best Practices

### 1. **Start Conservative**
- Begin with low concurrency (2-5)
- Monitor resource usage
- Gradually increase based on performance

### 2. **Environment-Specific Settings**
- Development: Low concurrency for debugging
- Staging: Medium concurrency for testing
- Production: Optimized concurrency for performance

### 3. **Task-Specific Limits**
- API calls: Respect rate limits
- Database operations: Consider connection pools
- File operations: Consider I/O limits

### 4. **Monitor and Adjust**
- Use Prefect's built-in monitoring
- Track resource usage
- Adjust based on performance metrics

### 5. **Error Handling**
- Implement retry logic
- Handle concurrency-related errors
- Use circuit breakers for external services

## 🔍 Troubleshooting

### Common Issues

1. **Too High Concurrency**
   - Symptoms: Resource exhaustion, timeouts, errors
   - Solution: Reduce `max_workers` or `concurrency_limit`

2. **Too Low Concurrency**
   - Symptoms: Slow processing, underutilized resources
   - Solution: Increase concurrency limits

3. **API Rate Limits**
   - Symptoms: 429 errors, throttling
   - Solution: Reduce concurrency or implement backoff

4. **Database Connection Limits**
   - Symptoms: Connection pool exhaustion
   - Solution: Reduce concurrency or increase pool size

### Debugging Commands

```bash
# Check current configuration
make list-config

# Run with specific concurrency
make run-rpa3-dev  # Uses development settings (5 workers)

# Monitor resource usage
htop  # or your preferred system monitor
```

## 📈 Measuring Performance

### Key Metrics

1. **Throughput**: Items processed per minute
2. **Latency**: Average processing time per item
3. **Resource Usage**: CPU, memory, network
4. **Error Rate**: Failed tasks percentage

### Example Monitoring

```python
import time
from prefect import get_run_logger

@task
def monitored_task(data: dict) -> dict:
    logger = get_run_logger()
    start_time = time.time()
    
    try:
        result = process_data(data)
        duration = time.time() - start_time
        logger.info(f"Task completed in {duration:.2f}s")
        return result
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Task failed after {duration:.2f}s: {e}")
        raise
```

## 🎯 Conclusion

Concurrency control is essential for building robust, scalable Prefect workflows. By understanding the different methods and applying them appropriately, you can optimize your workflows for both performance and resource efficiency.

Remember:
- Start with conservative settings
- Monitor performance and adjust
- Use environment-specific configurations
- Consider task-specific requirements
- Always test in staging before production
