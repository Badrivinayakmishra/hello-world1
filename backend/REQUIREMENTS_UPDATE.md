# Requirements Update for Background Jobs

## New Dependencies (Add to requirements.txt)

```txt
# Background Job Processing
celery==5.3.4
redis==5.0.1
kombu==5.3.4  # Celery messaging library
```

## Installation

```bash
# Activate virtual environment
source venv/bin/activate  # or venv312/bin/activate for Python 3.12

# Install new dependencies
pip install celery==5.3.4 redis==5.0.1 kombu==5.3.4

# Or update from requirements.txt after adding the above
pip install -r requirements.txt
```

## Redis Installation

### macOS (Homebrew)
```bash
brew install redis
brew services start redis

# Check if running
redis-cli ping
# Should return: PONG
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Check if running
redis-cli ping
```

### Docker
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Check if running
docker exec -it redis redis-cli ping
```

## Running Celery Worker

### Development (Local)
```bash
# Terminal 1: Start Redis (if not already running)
redis-server

# Terminal 2: Start Celery Worker
cd /path/to/backend
celery -A celery_app worker --loglevel=info

# Terminal 3: Start Flask App
python app_v2.py
```

### Production (Supervisor)

Create `/etc/supervisor/conf.d/celery.conf`:

```ini
[program:celery_worker]
command=/path/to/venv/bin/celery -A celery_app worker --loglevel=info --concurrency=4
directory=/path/to/backend
user=www-data
numprocs=1
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
stopasgroup=true
killasgroup=true
```

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start celery_worker
```

### Production (Systemd)

Create `/etc/systemd/system/celery.service`:

```ini
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/backend
ExecStart=/path/to/venv/bin/celery -A celery_app worker --detach --loglevel=info --concurrency=4
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl start celery
sudo systemctl enable celery
```

## Monitoring

### Flower (Celery monitoring tool)
```bash
# Install
pip install flower

# Run
celery -A celery_app flower --port=5555

# Open http://localhost:5555 in browser
```

### Check Redis
```bash
# Connect to Redis
redis-cli

# Inside redis-cli:
KEYS *  # List all keys
INFO  # Redis server info
DBSIZE  # Number of keys
FLUSHDB  # Clear database (CAREFUL!)
```

## Environment Variables

Add to `.env` or environment:

```bash
# Redis URL (default uses localhost)
REDIS_URL=redis://localhost:6379/0

# For Redis with password
REDIS_URL=redis://:password@localhost:6379/0

# For Redis Cloud
REDIS_URL=redis://username:password@redis-host:port/0
```

## Testing Background Jobs

### Test Sync Task
```bash
curl -X POST http://localhost:5003/api/integrations/gmail/sync \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json"

# Response will include job_id:
# {"success": true, "job_id": "abc123...", ...}
```

### Check Job Status
```bash
curl http://localhost:5003/api/jobs/abc123... \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Response:
# {
#   "success": true,
#   "job": {
#     "task_id": "abc123...",
#     "state": "PROGRESS",
#     "percent": 45,
#     "status": "Processing document 45/100..."
#   }
# }
```

### Cancel Job
```bash
curl -X POST http://localhost:5003/api/jobs/abc123.../cancel \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"terminate": false}'
```

## Task Queue Configuration

Configured queues:
- `default` (priority 5): Sync tasks, embedding tasks
- `high_priority` (priority 10): Gap analysis tasks
- `low_priority` (priority 1): Video generation tasks

## Troubleshooting

### Celery worker not starting
```bash
# Check Redis connection
redis-cli ping

# Check Python path
which python
which celery

# Run with verbose logging
celery -A celery_app worker --loglevel=debug
```

### Tasks stuck in PENDING
- Redis might be down: `redis-cli ping`
- Celery worker might not be running: Check logs
- Wrong broker URL: Check `REDIS_URL` environment variable

### Tasks failing silently
- Check Celery worker logs
- Check task retry settings in `celery_app.py`
- Verify database connection in tasks

## Performance Tuning

### Concurrency
```bash
# More workers for I/O-bound tasks
celery -A celery_app worker --concurrency=10

# Use gevent for high concurrency
pip install gevent
celery -A celery_app worker --pool=gevent --concurrency=100
```

### Memory Management
```bash
# Restart workers after N tasks (prevent memory leaks)
celery -A celery_app worker --max-tasks-per-child=1000
```

### Prefetching
```bash
# Don't prefetch tasks (better distribution across workers)
celery -A celery_app worker --prefetch-multiplier=1
```

## Cost Optimization

- Use Redis persistence for production (RDB or AOF)
- Set reasonable `result_expires` (default: 1 hour)
- Clean up old results periodically
- Use separate queues for expensive vs cheap tasks
- Monitor queue lengths and adjust worker count

## Security

- Use Redis password: `REDIS_URL=redis://:password@host:port/0`
- Enable Redis AUTH: `requirepass` in redis.conf
- Use SSL/TLS for Redis: `rediss://` (note the 's')
- Limit Redis network exposure: `bind 127.0.0.1` in redis.conf
- Use separate Redis databases for different environments

## Next Steps

1. ✅ Install Redis
2. ✅ Install Celery dependencies
3. ✅ Start Celery worker
4. ✅ Test sync task via API
5. ⚠️ Update frontend to poll job status (see frontend update below)
6. ⚠️ Set up production deployment (Supervisor or Systemd)
7. ⚠️ Configure monitoring (Flower)

## Frontend Integration

Frontend needs to be updated to poll for job status:

```typescript
// Start sync
const startSync = async () => {
  const response = await axios.post(`${API_BASE}/integrations/gmail/sync`)
  const jobId = response.data.job_id

  // Poll for status
  const pollInterval = setInterval(async () => {
    const status = await axios.get(`${API_BASE}/jobs/${jobId}`)

    setProgress(status.data.job.percent)
    setStatusMessage(status.data.job.status)

    if (status.data.job.state === 'SUCCESS') {
      clearInterval(pollInterval)
      alert('Sync completed!')
      loadDocuments()  // Refresh data
    } else if (status.data.job.state === 'FAILURE') {
      clearInterval(pollInterval)
      alert('Sync failed: ' + status.data.job.error)
    }
  }, 2000)  // Poll every 2 seconds
}
```
