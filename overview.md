## 1. System Overview

1. **Crawler Layer**
   – **Scrapy** (Python) spiders for structured sites (careers pages, university portals)
   – **Headless browser** (Playwright or Selenium) for dynamically-rendered pages or JavaScript-heavy sites
   – **Social-media connectors**: RSS feeds where available; or official APIs (e.g. Twitter Academic API, LinkedIn Learning if you qualify)

2. **Data Extraction & Storage**
   – **BeautifulSoup / lxml** to parse HTML and extract title, description, deadlines, links
   – Store raw and cleaned records in **MongoDB Atlas** (free tier) or **PostgreSQL** (Heroku Postgres Student Plan)

3. **AI-Powered Filtering & Classification**
   – Use **OpenAI embeddings** or **Hugging Face transformers** (e.g. `sentence-transformers`) to vectorize opportunity descriptions
   – Maintain a set of “interest” vectors (e.g. “computer science internships,” “PhD funding,” etc.)
   – Compute similarity scores and tag each item (job/internship/etc.)
   – Optionally fine-tune a small classifier (scikit-learn, logistic regression or a tiny neural net) on examples you label

4. **Aggregation & Deduplication**
   – Batch jobs daily: remove duplicates (by title + link fingerprint), rank by recency and relevance score
   – Prepare a templated HTML/text email

5. **Email Scheduler**
   – Use **Celery Beat** (with Redis on free Render or Heroku Redis) or plain **cron** on your host
   – Send via **SendGrid** or **Mailgun** (both offer free tiers under a student account)

6. **Hosting & Deployment**
   – **Heroku** (free dyno with student pack) or **Render**/**Fly.io** for Python apps
   – Store code in **GitHub**, trigger deploys on push
   – Use **GitHub Actions** to run daily cron if you prefer serverless

---

## 2. Recommended Tech Stack

| Layer             | Technology                                    | Why                                   |
| ----------------- | --------------------------------------------- | ------------------------------------- |
| Web crawling      | Scrapy + Playwright                           | Scalable spiders + JS rendering       |
| Parsing           | BeautifulSoup / lxml                          | Battle-tested HTML parsing            |
| Data storage      | MongoDB Atlas (free) or Heroku Postgres       | Flexible schema / relational querying |
| AI classification | OpenAI API (embeddings + GPT) or Hugging Face | Easy semantic filtering               |
| Task scheduling   | Celery Beat + Redis or cron                   | Reliable periodic execution           |
| Email delivery    | SendGrid / Mailgun                            | Generous free tier, SMTP API          |
| CI/CD + repo      | GitHub + GitHub Actions                       | Automate testing, linting, deploy     |
| Hosting           | Heroku / Render / Fly.io                      | Free student tiers, simple deploy     |

---

## 3. Component Breakdown

### A. Crawlers

* **Scrapy project** with one spider per domain-type:

  ```bash
  scrapy startproject opp_aggregator
  cd opp_aggregator
  scrapy genspider company_careers example.com
  ```
* **Playwright** for dynamic pages:

  ```python
  from playwright.sync_api import sync_playwright

  def fetch_with_playwright(url):
      with sync_playwright() as p:
          browser = p.chromium.launch(headless=True)
          page = browser.new_page()
          page.goto(url)
          html = page.content()
          browser.close()
      return html
  ```

### B. Extraction & Normalization

* Write extractors that map raw HTML into a common schema:

  ```python
  {
    "title": str,
    "description": str,
    "deadline": date,
    "type": "job"|"internship"|"scholarship"|"research",
    "link": str,
    "source": str
  }
  ```
* Clean dates with `dateparser`, normalize text via `nlp = spacy.load("en_core_web_sm")`.

### C. AI-Based Filtering

* **Embeddings pipeline**:

  ```python
  from openai import OpenAI
  client = OpenAI()

  def embed(text):
      return client.embeddings.create(input=text, model="text-embedding-ada-002")["data"][0]["embedding"]
  ```
* Compare with your “interest” embeddings via cosine similarity to keep top-K relevant.

### D. Scheduling & Email

* **Celery** with Redis:

  ```python
  from celery import Celery

  app = Celery("tasks", broker="redis://...")

  @app.on_after_configure.connect
  def setup_periodic_tasks(sender, **_):
      sender.add_periodic_task(24*60*60, aggregate_and_email.s(), name="daily at 7am")

  @app.task
  def aggregate_and_email():
      items = query_today_items()
      html = render_template("daily_digest.html", items=items)
      send_email("Your Daily Opportunities", to=YOU, html=html)
  ```
* Or simply add a cron job on your host that runs `python send_digest.py`.

---

## 4. Hosting & Student-Pack Credits

1. **GitHub Student Developer Pack**
   – Free credits for Heroku, DigitalOcean, MongoDB Atlas, SendGrid, etc.

2. **Deploy on Heroku**

   * Push your code; heroku CLI:

     ```bash
     heroku create opp-aggregator
     git push heroku main
     heroku addons:create heroku-postgresql:hobby-dev
     heroku addons:create sendgrid:starter
     ```
   * Set config vars (`OPENAI_API_KEY`, `SENDGRID_API_KEY`, etc.)

3. **Alternatives**

   * **Render.com** — free web services + Redis
   * **Fly.io** — free small VMs, easy Docker deploy

---

## 5. Next Steps

1. **Prototype** your crawler for 1–2 target sites.
2. **Design** and implement the common data schema + storage.
3. **Integrate** OpenAI (or HF) to score relevance.
4. **Build** the email templating and scheduling component.
5. **Deploy** using your student-pack credits and schedule daily runs.

With this modular approach you’ll have a flexible, AI-driven aggregator that keeps you on top of every opportunity—delivered to your inbox each morning. Good luck!

