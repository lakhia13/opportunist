# Opportunist - AI-Driven Opportunity Aggregator

🚀 An intelligent system that automatically discovers, filters, and delivers personalized opportunities (jobs, internships, scholarships, research positions, competitions, and grants) directly to your inbox every morning.

## Features

- **Automated Crawling**: Scrapes company career pages, university portals, and scholarship boards
- **AI-Powered Filtering**: Uses OpenAI embeddings or SentenceTransformers for relevance scoring
- **Smart Deduplication**: Prevents duplicate opportunities using content hashing
- **Daily Email Digests**: Beautiful HTML emails delivered at 7:00 AM with fresh opportunities
- **Modular Architecture**: Microservices design for scalability and maintainability
- **Free Tier Friendly**: Designed to run within student pack free tier limits

## Architecture

```
[Crawler Service] → [AI Filter Service] → [Database] → [Email Service]
                                           ↑
                                    [Scheduler]
```

### Core Components

1. **Crawler Layer**: Scrapy + Playwright for web scraping
2. **AI Processing**: OpenAI embeddings or local SentenceTransformers
3. **Storage**: MongoDB Atlas with TTL indexes
4. **Scheduling**: Celery Beat or simple cron-like scheduler
5. **Email Delivery**: SendGrid with HTML templates

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/your-username/opportunist.git
cd opportunist

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env
```

**Required Configuration:**

```env
# MongoDB (MongoDB Atlas free tier)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/opportunist

# OpenAI (for embeddings)
OPENAI_API_KEY=sk-your-openai-api-key

# SendGrid (for emails)
SENDGRID_API_KEY=SG.your-sendgrid-api-key
SENDGRID_FROM_EMAIL=your-email@domain.com
SENDGRID_TO_EMAIL=recipient@domain.com
```

### 3. Initialize Application

```bash
# Initialize database and services
python main.py init

# Test email configuration
python main.py test-email your-email@domain.com

# Run a test pipeline
python main.py run full_pipeline
```

### 4. Start Scheduler

```bash
# Start the daily scheduler
python main.py start
```

## Usage

### Command Line Interface

```bash
# Get help
python main.py --help

# Check system status
python main.py status

# Add a new user
python main.py add-user new-user@domain.com

# Run specific tasks manually
python main.py run crawl
python main.py run process
python main.py run send_emails
python main.py run full_pipeline

# Clean up old data
python main.py cleanup --days 7

# Start with debug logging
python main.py --debug start
```

### Manual Task Execution

```python
# Run crawling only
python main.py run crawl

# Process and filter opportunities
python main.py run process

# Send email digests
python main.py run send_emails

# Complete pipeline
python main.py run full_pipeline
```

## Configuration

### User Interests

Edit `src/config.py` to customize the interests used for AI filtering:

```python
USER_INTERESTS = [
    "computer science internships",
    "software engineering jobs",
    "machine learning research",
    "PhD funding opportunities",
    "data science positions",
    # Add your interests here
]
```

### Target Domains

Configure which domains to crawl in `src/config.py`:

```python
TARGET_DOMAINS = {
    "companies": [
        "careers.google.com",
        "jobs.netflix.com",
        "careers.microsoft.com",
        # Add more company domains
    ],
    "universities": [
        "mit.edu",
        "stanford.edu",
        # Add university domains
    ]
}
```

### Email Schedule

Modify the email delivery time:

```env
EMAIL_SCHEDULE_TIME=07:00
TIMEZONE=America/New_York
```

## Monitoring and Debugging

### Check System Status

```bash
python main.py status
```

Output:
```
=== Pipeline Status ===
Timestamp: 2025-01-27T10:30:00
Total opportunities (24h): 45

Opportunities by category:
  job: 20
  internship: 10
  scholarship: 8
  research: 5
  competition: 2

=== Health Status ===
Overall status: healthy
  ✅ database: healthy
  ✅ embedding_service: healthy
  ✅ email_service: healthy
  ✅ crawl_activity: healthy
```

### Log Files

Logs are written to:
- Console (formatted with colors)
- `logs/opportunist.log` (rotated daily)

### Debug Mode

```bash
python main.py --debug status
python main.py --debug run full_pipeline
```

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions including:

- Heroku deployment
- Render.com deployment
- Docker containerization
- Environment variable management
- Monitoring and alerting

## Development

### Project Structure

```
opportunist/
├── src/
│   ├── config.py              # Configuration and settings
│   ├── models/                # Data models
│   ├── database/              # Database layer (MongoDB)
│   ├── crawlers/              # Web crawling components
│   ├── ai/                    # AI/ML components
│   ├── services/              # Business logic services
│   └── templates/             # Email templates
├── main.py                    # CLI entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
└── README.md                  # This file
```

### Adding New Crawlers

1. Create a new crawler class inheriting from `BaseCrawler`
2. Implement `extract_opportunities()` and `get_entry_points()`
3. Add to the orchestrator service

Example:

```python
from src.crawlers.base_crawler import BaseCrawler

class MyCustomCrawler(BaseCrawler):
    async def get_entry_points(self):
        return ["https://example.com/careers"]
    
    async def extract_opportunities(self, html_content, source_url):
        # Parse HTML and extract opportunities
        opportunities = []
        # ... parsing logic ...
        return opportunities
```

### Testing

```bash
# Test individual components
python -m pytest tests/

# Test email functionality
python main.py test-email your-email@domain.com

# Test crawler
python main.py run crawl

# Test full pipeline
python main.py run full_pipeline
```

## Cost Management

### Free Tier Usage

| Service | Free Tier Limit | Usage |
|---------|----------------|-------|
| MongoDB Atlas | 512 MB | ~100K opportunities |
| OpenAI API | $5 credits | ~500K tokens/month |
| SendGrid | 100 emails/day | Daily digests |
| Heroku/Render | 550 hours/month | Always-on hosting |

### Optimization Tips

1. **Rate Limiting**: Configure `CRAWL_DELAY` to respect site limits
2. **Batch Processing**: Process embeddings in batches
3. **TTL Indexes**: Old data auto-expires from MongoDB
4. **Relevance Threshold**: Higher threshold = fewer opportunities = lower costs

## FAQ

**Q: How do I add more opportunity sources?**
A: Add domains to `TARGET_DOMAINS` in `config.py` or create custom crawlers.

**Q: Can I run this locally only?**
A: Yes! Use local MongoDB and skip cloud deployment. Email delivery requires SendGrid.

**Q: How accurate is the AI filtering?**
A: Depends on your interests definition. Start with broad keywords and refine based on results.

**Q: What if I hit API rate limits?**
A: The system has built-in retry logic and respects rate limits. Adjust `CRAWL_DELAY` if needed.

**Q: Can I customize the email template?**
A: Yes! Create `src/templates/daily_digest.html` or modify the default template in `email_service.py`.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check the logs in `logs/opportunist.log`
- Run with `--debug` flag for verbose output
