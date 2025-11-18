# Docker Setup Fixed ✅

## Changes Made

### 1. **requirements.txt** - Added Missing Packages
- `langchain-core` - Required for messages
- `langchain-community` - Required for DuckDuckGoSearchRun
- `fastmcp` - Required for MCP client
- `pydantic-settings` - Required for BaseSettings
- `loguru` - Required for logging
- `uvicorn[standard]` - Full uvicorn with websockets
- `httpx` - HTTP client
- `psycopg2-binary` - PostgreSQL adapter
- Updated version pins for compatibility

### 2. **Dockerfile** - Fixed Build Context
**Before:**
```dockerfile
COPY phase2/requirements.txt /app/phase2/requirements.txt
RUN pip install --no-cache-dir -r /app/phase2/requirements.txt
COPY . /app/
```

**After:**
```dockerfile
COPY . /app/  # Copy first
RUN pip install --no-cache-dir -r /app/phase2/requirements.txt  # Then install
ENV PYTHONPATH=/app:/app/phase2  # Add both to path
WORKDIR /app/phase2  # Set working directory
```

**Why:** Build context is parent directory, so paths were wrong

### 3. **docker-compose.yml** - Fixed Commands
**Before:**
```yaml
command: python hypothesis_generator/generator.py
working_dir: /app/phase2
```

**After:**
```yaml
command: python -m hypothesis_generator.generator
# working_dir already set in Dockerfile
```

**Why:** Module imports work better than direct file execution

### 4. **Added __init__.py Files**
Created missing `__init__.py` in:
- `phase2/__init__.py`
- `config/__init__.py`
- `hypothesis_generator/__init__.py`
- `risk_managers/__init__.py`
- `backtesting/__init__.py`
- `database/__init__.py`

**Why:** Makes directories proper Python packages for module imports

---

## How to Build and Run

### Option 1: Build Fresh (Recommended First Time)
```bash
cd phase2
docker-compose build --no-cache
docker-compose up
```

### Option 2: Quick Start (After First Build)
```bash
cd phase2
docker-compose up
```

### Option 3: Rebuild Single Service
```bash
docker-compose build hypothesis-generator
docker-compose up hypothesis-generator
```

### Option 4: Run in Background
```bash
docker-compose up -d
docker-compose logs -f  # View logs
```

---

## Service URLs

Once running:
- **Hypothesis Generator MCP:** `http://localhost:9000/mcp/`
- **Hypothesis Query API:** `http://localhost:8002`
- **Risk Managers MCP:** `http://localhost:9001/mcp/`
- **Backtesting API:** `http://localhost:8001`
- **PostgreSQL:** `localhost:5432`
- **Redis:** `localhost:6379`

---

## Testing Individual Services

### Test Backtesting API
```bash
curl http://localhost:8001/health
```

### Test Hypothesis API
```bash
curl http://localhost:8002/health
```

### Test Redis
```bash
docker exec -it phase2-redis redis-cli ping
```

### Test PostgreSQL
```bash
docker exec -it phase2-postgres psql -U postgres -d trading_system -c "\dt"
```

---

## Common Issues and Fixes

### Issue: "No module named 'langchain_openai'"
**Fix:** Already fixed in requirements.txt

### Issue: "Cannot import name 'RiskManagerPrompts'"
**Fix:** Already fixed - changed to relative import

### Issue: "Module not found" errors
**Fix:** Added __init__.py files to all directories

### Issue: Build context errors
**Fix:** Dockerfile now copies from correct context

### Issue: Services can't find each other
**Solution:** Use service names as hostnames:
- `http://redis:6379`
- `http://hypothesis-generator:9000/mcp/`
- `http://risk-managers:9001/mcp/`
- `http://backtesting-api:8001`

---

## Environment Variables

Make sure `.env` file has:
```bash
OPENAI_API_KEY=your-key-here
PATHWAY_LICENSE_KEY=your-key-here  # Optional

# Services use internal network names:
REDIS_HOST=redis
POSTGRES_HOST=postgres
RISK_ANALYSIS_MCP_URL=http://risk-managers:9001/mcp/
HYPOTHESIS_MCP_URL=http://hypothesis-generator:9000/mcp/
BACKTESTING_API_URL=http://backtesting-api:8001
```

---

## Cleanup

### Stop All Services
```bash
docker-compose down
```

### Stop and Remove Volumes (Fresh Start)
```bash
docker-compose down -v
```

### Remove All Images
```bash
docker-compose down --rmi all
```

### Full Cleanup
```bash
docker-compose down -v --rmi all
docker system prune -af
```

---

## Next Steps

1. ✅ Build containers: `docker-compose build`
2. ✅ Start services: `docker-compose up`
3. 🧪 Test individual services using curl commands above
4. 📝 Check logs: `docker-compose logs -f <service-name>`
5. 🐛 Debug: `docker exec -it <container-name> /bin/bash`

---

## Quick Reference

```bash
# Build and start
docker-compose up --build

# View logs
docker-compose logs -f orchestrator
docker-compose logs -f hypothesis-generator

# Restart single service
docker-compose restart backtesting-api

# Enter container
docker exec -it phase2-orchestrator /bin/bash

# Check running containers
docker-compose ps

# Stop everything
docker-compose down
```
