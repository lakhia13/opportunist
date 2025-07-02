# Deployment Guide

This guide covers deploying the Opportunist application to various cloud platforms using student pack credits and free tiers.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Heroku Deployment](#heroku-deployment)
4. [Render.com Deployment](#rendercom-deployment)
5. [Fly.io Deployment](#flyio-deployment)
6. [Docker Deployment](#docker-deployment)
7. [Database Setup (MongoDB Atlas)](#database-setup-mongodb-atlas)
8. [Email Setup (SendGrid)](#email-setup-sendgrid)
9. [Monitoring and Maintenance](#monitoring-and-maintenance)
10. [Troubleshooting](#troubleshooting)

## Prerequisites

- Python 3.8+
- Git
- GitHub Student Developer Pack (recommended)
- MongoDB Atlas account
- SendGrid account
- OpenAI API account (optional, can use local models)

## Environment Setup

### 1. GitHub Student Pack

Sign up for the [GitHub Student Developer Pack](https://education.github.com/pack) to get:
- Free Heroku dyno hours
- MongoDB Atlas credits
- DigitalOcean credits
- And many other services

### 2. Required API Keys

Gather these credentials before deployment:

```env
# MongoDB Atlas
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net/opportunist?retryWrites=true&w=majority

# OpenAI (for AI features)
OPENAI_API_KEY=sk-your-openai-api-key

# SendGrid (for email delivery)
SENDGRID_API_KEY=SG.your-sendgrid-api-key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
SENDGRID_TO_EMAIL=your-email@domain.com

# Redis (for Celery, if using)
REDIS_URL=redis://localhost:6379/0
```

## Heroku Deployment

### 1. Setup Heroku CLI

```bash
# Install Heroku CLI
curl https://cli-assets.heroku.com/install.sh | sh

# Login to Heroku
heroku login
```

### 2. Create Heroku App

```bash
# Create new Heroku application
heroku create your-opportunist-app

# Add Python buildpack
heroku buildpacks:add heroku/python
```

### 3. Configure Add-ons

```bash
# Add Redis for Celery (optional)
heroku addons:create heroku-redis:mini

# Add SendGrid for emails
heroku addons:create sendgrid:starter
```

### 4. Set Environment Variables

```bash
# Set all required environment variables
heroku config:set MONGODB_URI="mongodb+srv://..."
heroku config:set OPENAI_API_KEY="sk-..."
heroku config:set SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
heroku config:set SENDGRID_TO_EMAIL="your-email@domain.com"
heroku config:set ENVIRONMENT="production"
heroku config:set LOG_LEVEL="INFO"

# SendGrid API key should be auto-set by the add-on
# If not, set it manually:
# heroku config:set SENDGRID_API_KEY="SG..."
```

### 5. Create Heroku Files

Create `Procfile`:

```bash
cat > Procfile << 'EOF'
web: python main.py start
worker: celery -A src.services.scheduler.celery_app worker --loglevel=info
beat: celery -A src.services.scheduler.celery_app beat --loglevel=info
EOF
```

Create `runtime.txt`:

```bash
echo "python-3.11.0" > runtime.txt
```

### 6. Deploy

```bash
# Add files to git
git add Procfile runtime.txt
git commit -m "Add Heroku deployment files"

# Deploy to Heroku
git push heroku main

# Scale dynos (if using Celery)
heroku ps:scale web=1 worker=1 beat=1

# For simple scheduler (no Celery)
heroku ps:scale web=1
```

### 7. Initialize Application

```bash
# Initialize the application
heroku run python main.py init

# Test email configuration
heroku run python main.py test-email your-email@domain.com

# Check application logs
heroku logs --tail
```

## Render.com Deployment

### 1. Create render.yaml

```yaml
services:
  - type: web
    name: opportunist
    env: python
    plan: starter  # Free tier
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python main.py start"
    envVars:
      - key: ENVIRONMENT
        value: production
      - key: LOG_LEVEL
        value: INFO
      - key: MONGODB_URI
        sync: false  # Set in dashboard
      - key: OPENAI_API_KEY
        sync: false  # Set in dashboard
      - key: SENDGRID_API_KEY
        sync: false  # Set in dashboard
      - key: SENDGRID_FROM_EMAIL
        sync: false
      - key: SENDGRID_TO_EMAIL
        sync: false
      - key: REDIS_URL
        fromService:
          type: redis
          name: opportunist-redis
          property: connectionString

  - type: redis
    name: opportunist-redis
    plan: starter  # Free tier
    maxmemoryPolicy: allkeys-lru
```

### 2. Deploy to Render

1. Push code to GitHub
2. Connect GitHub repository to Render
3. Set environment variables in Render dashboard
4. Deploy application

### 3. Manual Environment Variables

Set these in the Render dashboard:

```
MONGODB_URI=mongodb+srv://...
OPENAI_API_KEY=sk-...
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
SENDGRID_TO_EMAIL=your-email@domain.com
```

## Fly.io Deployment

### 1. Install Fly CLI

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
fly auth login
```

### 2. Initialize Fly App

```bash
# Initialize Fly application
fly launch --no-deploy

# This creates fly.toml configuration file
```

### 3. Configure fly.toml

```toml
app = "your-opportunist-app"
primary_region = "ord"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  ENVIRONMENT = "production"
  LOG_LEVEL = "INFO"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1

[services.concurrency]
  type = "connections"
  hard_limit = 25
  soft_limit = 20
```

### 4. Set Secrets

```bash
# Set environment variables as secrets
fly secrets set MONGODB_URI="mongodb+srv://..."
fly secrets set OPENAI_API_KEY="sk-..."
fly secrets set SENDGRID_API_KEY="SG..."
fly secrets set SENDGRID_FROM_EMAIL="noreply@yourdomain.com"
fly secrets set SENDGRID_TO_EMAIL="your-email@domain.com"
```

### 5. Deploy

```bash
# Deploy application
fly deploy

# Check status
fly status

# View logs
fly logs
```

## Docker Deployment

### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port (if running web interface)
EXPOSE 8080

# Run the application
CMD ["python", "main.py", "start"]
```

### 2. Create docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SENDGRID_API_KEY=${SENDGRID_API_KEY}
      - SENDGRID_FROM_EMAIL=${SENDGRID_FROM_EMAIL}
      - SENDGRID_TO_EMAIL=${SENDGRID_TO_EMAIL}
      - REDIS_URL=redis://redis:6379/0
      - ENVIRONMENT=production
    depends_on:
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data

  # Optional: Celery worker for production
  worker:
    build: .
    command: celery -A src.services.scheduler.celery_app worker --loglevel=info
    environment:
      - MONGODB_URI=${MONGODB_URI}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

  # Optional: Celery beat scheduler
  beat:
    build: .
    command: celery -A src.services.scheduler.celery_app beat --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    restart: unless-stopped

volumes:
  redis_data:
```

### 3. Build and Run

```bash
# Build and run with docker-compose
docker-compose up -d

# Check logs
docker-compose logs -f

# Initialize application
docker-compose exec app python main.py init

# Stop services
docker-compose down
```

## Database Setup (MongoDB Atlas)

### 1. Create MongoDB Atlas Cluster

1. Go to [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Sign up with GitHub Student Pack for credits
3. Create a new cluster (choose M0 free tier)
4. Select a cloud provider and region
5. Create cluster (takes 1-3 minutes)

### 2. Configure Database Access

1. **Database Access**:
   - Create a database user
   - Set username and password
   - Grant "Atlas Admin" role (or custom role)

2. **Network Access**:
   - Add IP addresses that can access the cluster
   - For development: Add current IP
   - For production: Add "0.0.0.0/0" (all IPs) or specific cloud provider IPs

### 3. Get Connection String

1. Click "Connect" on your cluster
2. Choose "Connect your application"
3. Select Python driver
4. Copy the connection string
5. Replace `<password>` with your database password

## Email Setup (SendGrid)

### 1. Create SendGrid Account

1. Go to [SendGrid](https://sendgrid.com)
2. Sign up (100 emails/day free)
3. Verify your email address

### 2. Create API Key

1. Go to Settings > API Keys
2. Create a new API key
3. Give it "Full Access" or "Mail Send" permissions
4. Copy the API key (starts with `SG.`)

### 3. Domain Authentication (Optional)

For better deliverability:

1. Go to Settings > Sender Authentication
2. Choose "Authenticate Your Domain"
3. Follow DNS configuration steps
4. Use your authenticated domain in `SENDGRID_FROM_EMAIL`

### 4. Test Email Delivery

```bash
# Test email configuration
python main.py test-email your-email@domain.com

# Check SendGrid activity
# Go to SendGrid dashboard > Activity
```

## Monitoring and Maintenance

### 1. Health Checks

```bash
# Check application status
heroku run python main.py status

# Or via API endpoint (if implemented)
curl https://your-app.herokuapp.com/health
```

### 2. Log Monitoring

```bash
# Heroku logs
heroku logs --tail

# Render logs
# Check in Render dashboard

# Docker logs
docker-compose logs -f app
```

### 3. Resource Monitoring

**Heroku:**
```bash
# Check dyno usage
heroku ps

# Check add-on usage
heroku addons
```

**MongoDB Atlas:**
- Monitor in Atlas dashboard
- Set up alerts for storage usage
- Track query performance

**SendGrid:**
- Monitor email delivery rates
- Check for bounces/spam complaints
- Track API usage

### 4. Automated Monitoring

Set up monitoring with:
- **Uptime monitoring**: Pingdom, UptimeRobot
- **Error tracking**: Sentry
- **Performance monitoring**: New Relic
- **Log aggregation**: Papertrail, Loggly

### 5. Backup Strategy

**Database Backups:**
- MongoDB Atlas provides continuous backups
- Download periodic exports for critical data

**Code Backups:**
- Keep code in Git repository
- Tag releases for easy rollbacks

## Troubleshooting

### Common Issues

#### 1. Application Won't Start

```bash
# Check logs for errors
heroku logs --tail

# Common causes:
# - Missing environment variables
# - Database connection issues
# - Invalid Python version
```

#### 2. Database Connection Errors

```bash
# Test MongoDB connection
python -c "from pymongo import MongoClient; print(MongoClient('your-mongodb-uri').admin.command('ping'))"

# Check:
# - Connection string format
# - Username/password
# - Network access whitelist
# - SSL/TLS settings
```

#### 3. Email Delivery Issues

```bash
# Test SendGrid configuration
python main.py test-email your-email@domain.com

# Check:
# - API key validity
# - From email authentication
# - Spam folder
# - SendGrid activity dashboard
```

#### 4. Crawling Issues

```bash
# Test individual crawlers
python main.py run crawl

# Common issues:
# - Rate limiting
# - Website changes
# - Network connectivity
# - User-agent blocking
```

#### 5. Memory/Resource Issues

```bash
# Monitor resource usage
heroku logs --tail | grep "memory"

# Solutions:
# - Reduce batch sizes
# - Implement pagination
# - Use smaller embedding models
# - Clean up unused data
```

### Performance Optimization

1. **Database Optimization**:
   - Use appropriate indexes
   - Implement TTL for old data
   - Optimize queries

2. **Memory Optimization**:
   - Process in smaller batches
   - Use streaming for large datasets
   - Clean up objects after use

3. **Network Optimization**:
   - Implement request pooling
   - Use appropriate timeouts
   - Implement exponential backoff

### Scaling Considerations

#### When to Scale:
- High memory usage consistently
- Slow response times
- Queue backlogs
- Rate limit hits

#### Scaling Options:
- **Vertical**: Increase dyno size
- **Horizontal**: Add more workers
- **Queue-based**: Implement proper job queues
- **Caching**: Add Redis caching layer

## Security Best Practices

1. **Environment Variables**:
   - Never commit secrets to Git
   - Use platform-specific secret management
   - Rotate API keys regularly

2. **Database Security**:
   - Use strong passwords
   - Limit network access
   - Enable authentication
   - Regular security updates

3. **Application Security**:
   - Validate all inputs
   - Implement rate limiting
   - Use HTTPS everywhere
   - Keep dependencies updated

## Cost Management

### Free Tier Limits

| Service | Free Limit | Cost After Limit |
|---------|------------|-------------------|
| Heroku | 550 dyno hours/month | $7/month per dyno |
| MongoDB Atlas | 512 MB storage | $9/month for 2GB |
| SendGrid | 100 emails/day | $15/month for 40k emails |
| OpenAI | $5 credit | Pay per token |

### Cost Optimization Tips

1. **Use TTL indexes** to automatically clean old data
2. **Implement relevance thresholds** to reduce processing
3. **Batch API calls** to reduce request counts
4. **Monitor usage dashboards** regularly
5. **Set up billing alerts** on all services

## Maintenance Schedule

### Daily
- Monitor email delivery
- Check error logs
- Verify crawling activity

### Weekly
- Review performance metrics
- Check database usage
- Update environment if needed

### Monthly
- Update dependencies
- Review and optimize queries
- Clean up old logs
- Security updates

This concludes the comprehensive deployment guide. Choose the platform that best fits your needs and budget, and follow the respective deployment steps.
