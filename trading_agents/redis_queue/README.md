# Redis Queue System

Background job queue system using Redis Queue (RQ) for asynchronous trading workflow execution.

## 📋 Overview

This directory implements a job queue system that:
- Enqueues trading workflow requests
- Processes jobs in background workers
- Provides retry logic and error handling
- Tracks job status and results

## 🗂️ Files

- **task_queue.py** - Job enqueueing and queue management
- **worker.py** - Background worker process

## 🏗️ Architecture

```
API Request
    ↓
Enqueue Job (task_queue.py)
    ↓
Redis Queue
    ↓
Worker Picks Job (worker.py)
    ↓
Execute Workflow
    ↓
Store Result
    ↓
Return to API
```

## 📊 Task Queue

### Initialization

In `task_queue.py`:

```python
from redis import Redis
from rq import Queue

# Connect to Redis
redis_conn = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 1))  # DB 1 for job queue
)

# Create queue
q = Queue("trade_execution", connection=redis_conn)
```

### Enqueue Jobs

```python
def enqueue_trade(symbol: str, use_fallback: bool = False):
    """
    Enqueue trading workflow job
    
    Args:
        symbol: Stock ticker symbol
        use_fallback: Use sample data if reports unavailable
    
    Returns:
        job_id: RQ job ID
    """
    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    
    job = q.enqueue(
        "run_workflow.execute_trading_workflow",  # Function path
        symbol,
        trade_date,
        use_fallback,
        retry=Retry(max=3),      # Retry up to 3 times
        failure_ttl=86400        # Keep failed jobs 24h
    )
    
    return job.id
```

### Usage from API

```python
from redis_queue.task_queue import enqueue_trade

@app.post("/execute/{symbol}")
async def execute_workflow(symbol: str, use_fallback: bool = False):
    try:
        job_id = enqueue_trade(symbol, use_fallback)
        return {
            "status": "queued",
            "symbol": symbol,
            "job_id": job_id
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to enqueue: {e}")
```

## 🔄 Worker Process

### Worker Implementation

In `worker.py`:

```python
from rq import Worker, Queue, Connection
from redis import Redis

# Connect to Redis
redis_conn = Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=int(os.getenv("REDIS_DB", 1))
)

def main():
    """Start RQ worker"""
    with Connection(redis_conn):
        worker = Worker(
            ["trade_execution"],  # Queue names
            connection=redis_conn
        )
        print("[WORKER] Starting worker...")
        worker.work(with_scheduler=True)

if __name__ == "__main__":
    main()
```

### Worker Execution

```bash
# Start worker
python redis_queue/worker.py

# Output:
[WORKER] Starting worker...
[WORKER] Listening on queue: trade_execution
[WORKER] Job picked up: abc-123-def
[WORKER] Executing: execute_trading_workflow(AAPL, 2025-11-11_10-00-00, False)
[WORKER] Job completed: abc-123-def
```

## 📊 Job Lifecycle

### Job States

```
queued → started → finished
           ↓
         failed (with retry)
           ↓
       failed (max retries)
```

### Job Object

```python
from rq import Queue

job = q.enqueue(...)

# Job properties
job.id              # Unique job ID
job.status          # 'queued', 'started', 'finished', 'failed'
job.result          # Return value (when finished)
job.exc_info        # Exception info (when failed)
job.enqueued_at     # Timestamp
job.started_at      # Timestamp
job.ended_at        # Timestamp
```

### Check Job Status

```python
from rq import Queue
from rq.job import Job

job = Job.fetch(job_id, connection=redis_conn)

if job.is_finished:
    result = job.result
elif job.is_failed:
    error = job.exc_info
elif job.is_queued:
    position = job.get_position()
```

## 🔧 Configuration

### Queue Settings

```python
# Queue name
QUEUE_NAME = "trade_execution"

# Retry configuration
retry = Retry(max=3)  # Retry up to 3 times

# TTL settings
job_timeout = 3600      # Job timeout: 1 hour
result_ttl = 86400      # Keep results: 24 hours
failure_ttl = 86400     # Keep failures: 24 hours
```

### Redis Database

```bash
# Separate DBs for different purposes
REDIS_DB=0  # Pathway reports cache
REDIS_DB=1  # Trading agents job queue
```

## 🧪 Testing

### Test Job Enqueueing

```python
from redis_queue.task_queue import enqueue_trade

# Enqueue test job
job_id = enqueue_trade("AAPL", use_fallback=True)
print(f"Job enqueued: {job_id}")

# Check status
from rq.job import Job
from redis_queue.task_queue import redis_conn

job = Job.fetch(job_id, connection=redis_conn)
print(f"Status: {job.status}")
```

### Test Worker Locally

```bash
# Terminal 1: Start worker
python redis_queue/worker.py

# Terminal 2: Enqueue job
python -c "
from redis_queue.task_queue import enqueue_trade
job_id = enqueue_trade('AAPL', use_fallback=True)
print(f'Job ID: {job_id}')
"

# Terminal 1 will show:
# [WORKER] Job picked up: ...
# [WORKER] Executing workflow for AAPL
# [WORKER] Job completed
```

### Test Job Status API

```bash
# Enqueue job
JOB_ID=$(curl -s -X POST http://localhost:8001/execute/AAPL | jq -r .job_id)

# Check status
curl http://localhost:8001/job/$JOB_ID | jq

# Expected response:
{
  "job_id": "abc-123-def",
  "status": "finished",
  "result": {...},
  "enqueued_at": "2025-11-11T10:00:00Z",
  "started_at": "2025-11-11T10:00:05Z",
  "ended_at": "2025-11-11T10:02:30Z"
}
```

## 📊 Monitoring

### Queue Statistics

```python
from rq import Queue
from redis_queue.task_queue import redis_conn

q = Queue("trade_execution", connection=redis_conn)

# Queue stats
print(f"Queued: {len(q)}")
print(f"Jobs: {q.job_ids}")

# Failed queue
from rq.registry import FailedJobRegistry
failed = FailedJobRegistry(queue=q)
print(f"Failed: {failed.count}")
```

### Worker Status

```python
from rq import Worker

workers = Worker.all(connection=redis_conn)
for worker in workers:
    print(f"Worker: {worker.name}")
    print(f"State: {worker.state}")
    print(f"Current job: {worker.get_current_job()}")
```

### Redis CLI Commands

```bash
# Connect to Redis
docker exec -it redis redis-cli -n 1  # DB 1

# List queues
KEYS rq:queue:*

# Queue length
LLEN rq:queue:trade_execution

# List jobs
LRANGE rq:queue:trade_execution 0 -1

# Job details
GET rq:job:<job_id>

# Failed jobs
SMEMBERS rq:queue:trade_execution:failed
```

## 🔄 Retry Logic

### Automatic Retry

```python
job = q.enqueue(
    function,
    args,
    retry=Retry(max=3)  # Retry up to 3 times
)
```

### Retry on Specific Exceptions

```python
from rq import Retry
from requests.exceptions import Timeout

job = q.enqueue(
    function,
    args,
    retry=Retry(max=3, interval=[10, 30, 60])  # Backoff intervals
)
```

### Manual Retry

```bash
# Retry failed job
curl -X POST http://localhost:8001/job/{job_id}/retry
```

## 🛡️ Error Handling

### Worker Error Handling

```python
# In run_workflow.py
def execute_trading_workflow(symbol, trade_date, use_fallback):
    try:
        # Execute workflow
        result = run_workflow(symbol, use_fallback)
        return result
    except Exception as e:
        logger.error(f"Workflow failed for {symbol}: {e}")
        # Re-raise for RQ retry
        raise
```

### Failed Job Registry

```python
from rq.registry import FailedJobRegistry

failed_registry = FailedJobRegistry(queue=q)

# List failed jobs
for job_id in failed_registry.get_job_ids():
    job = Job.fetch(job_id, connection=redis_conn)
    print(f"Failed: {job.id}")
    print(f"Error: {job.exc_info}")
    
    # Optionally requeue
    # q.enqueue_job(job)
```

## 📈 Performance

### Throughput
- Jobs/second: ~10-20 (depends on workflow duration)
- Concurrent workers: Scalable (add more workers)
- Queue depth: Unlimited (Redis-backed)

### Resource Usage per Worker
- CPU: 10-20%
- Memory: 300-500 MB
- Network: Minimal (Redis local)

### Scaling

```bash
# Run multiple workers
python redis_queue/worker.py &  # Worker 1
python redis_queue/worker.py &  # Worker 2
python redis_queue/worker.py &  # Worker 3

# Workers share the queue
# Jobs distributed automatically
```

## 🔧 Advanced Configuration

### Job Priority

```python
# High priority queue
q_high = Queue("trade_execution_high", connection=redis_conn)

# Enqueue with priority
job = q_high.enqueue(function, args)

# Worker listens to multiple queues
worker = Worker(
    ["trade_execution_high", "trade_execution"],  # Priority order
    connection=redis_conn
)
```

### Scheduled Jobs

```python
from datetime import datetime, timedelta

# Schedule for future execution
job = q.enqueue_at(
    datetime.now() + timedelta(minutes=5),
    function,
    args
)

# Periodic scheduling (requires RQ Scheduler)
from rq_scheduler import Scheduler

scheduler = Scheduler(connection=redis_conn)
scheduler.schedule(
    scheduled_time=datetime.now(),
    func=function,
    args=[],
    interval=3600  # Run every hour
)
```

## 🔗 Related

- [../api/fastapi_server.py](../api/fastapi_server.py) - API enqueuing jobs
- [../run_workflow.py](../run_workflow.py) - Workflow execution function
- [RQ Documentation](https://python-rq.org/)

## 📝 Troubleshooting

### Jobs Not Processing
```bash
# Check worker is running
ps aux | grep worker.py

# Check Redis connection
redis-cli -n 1 PING

# Check queue
redis-cli -n 1 LLEN rq:queue:trade_execution
```

### Jobs Stuck in Queue
```bash
# Inspect queue
redis-cli -n 1 LRANGE rq:queue:trade_execution 0 -1

# Clear queue (caution!)
redis-cli -n 1 DEL rq:queue:trade_execution
```

### High Failure Rate
```bash
# Review failed jobs
from rq.registry import FailedJobRegistry
failed = FailedJobRegistry(queue=q)
for job_id in failed.get_job_ids():
    job = Job.fetch(job_id, connection=redis_conn)
    print(job.exc_info)
```
