**Software Requirements Specification (SRS)**
**Project:** Opportunist (AI-Driven Opportunity Aggregator)
**Date:** July 2, 2025
**Author:** \[pmldev]

---

### Table of Contents

1. Introduction
2. Overall Description
3. System Architecture
4. Functional Requirements & Components
   4.1 Crawler Component
   4.2 Extraction & Normalization Component
   4.3 Storage Component
   4.4 Filtering & Classification Component
   4.5 Aggregation & Deduplication Component
   4.6 Notification & Scheduling Component
5. External Interfaces
6. Data Model
7. Non-Functional Requirements
8. Deployment & Cost Constraints
9. Security & Privacy
10. Appendices

---

## 1. Introduction

**1.1 Purpose**
This SRS details requirements for a personal, AI-driven opportunity aggregator that automatically discovers and ranks jobs, internships, scholarships, research positions, competitions, grants, and similar listings from company and university websites as well as social media. It delivers a fresh, relevance-filtered email digest each morning.

**1.2 Scope**

* **Deployment:** Hosted on free-tier student cloud or self-hosted server.
* **Architecture:** Modular microservices (crawling, parsing, AI filtering, storage, scheduling).
* **Opportunities:** Categories include jobs, internships, scholarships, research roles, competitions, grants, and other edge-boosting listings.
* **Freshness:** Only items posted or updated within the past 24 hours are included, delivered daily at 07:00 AM America/New\_York.

**1.3 Definitions**

* **Opportunity:** Any academic, professional, or financial listing that can enhance the user’s profile.
* **Daily Freshness:** Content must be newly posted or updated within the last 24 hours.

---

## 2. Overall Description

**2.1 User Needs**

* **Comprehensive Coverage:** Crawl company careers pages, university portals, scholarship boards, Twitter, LinkedIn RSS feeds, and academic listservs.
* **Precision:** AI-based relevance ranking against user-defined interests.
* **Minimal Maintenance:** Config-driven lists of targets; automated daily operation.
* **Timeliness:** Guarantee that delivered items are fresh (≤24h old).

**2.2 Assumptions & Dependencies**

* Access to GitHub Student Pack credits (Heroku/Render, MongoDB Atlas, SendGrid).
* Respect for `robots.txt` and public API rate limits.
* Reliable internet connectivity for crawling and API calls.

---

## 3. System Architecture

A scalable microservice layout:

```
[Crawler Service] → [Extractor Service] → [Database] ↔ [Filter Service] → [Aggregator Service] → [Notifier Service]
```

* **Crawler Service:** Scrapy spiders + Playwright workers fetch pages.
* **Extractor Service:** Parses raw HTML into structured records.
* **Database:** MongoDB Atlas stores raw and processed documents.
* **Filter Service:** Uses OpenAI or SBERT embeddings to compute relevance scores.
* **Aggregator Service:** Selects, ranks, and deduplicates today’s items.
* **Notifier Service:** Schedules and sends daily digest via SendGrid.

---

## 4. Functional Requirements & Components

### 4.1 Crawler Component

* **Targets:** Configurable list of domains (company, university, scholarship boards, social feeds).
* **Tech:** Scrapy for static sites; Playwright headless browser for dynamic content.
* **Freshness Filter:** Only fetch pages updated within 24h if supported; otherwise timestamp crawled\_at.
* **Error Handling:** Retries up to 3 times; logs failures.

### 4.2 Extraction & Normalization Component

* **Parsing:** BeautifulSoup or lxml to extract title, description, deadline, posted date, link.
* **Schema:**

```json
{
  "title": "string",
  "description": "string",
  "deadline": "YYYY-MM-DD",
  "category": "job|internship|scholarship|research|competition|grant|other",
  "link": "url",
  "source": "string",
  "posted_at": "YYYY-MM-DDTHH:MM:SSZ",
  "crawled_at": "YYYY-MM-DDTHH:MM:SSZ"
}
```

* **Normalization:** dateparser for dates; spaCy for text cleanup; slugify links.

### 4.3 Storage Component

* **Database:** MongoDB Atlas free tier (512 MB).
* **Collections:** `raw_pages`, `opportunities`, `users`.
* **Indexes:** TTL index on `raw_pages`; compound index on `opportunities(posted_at, category)`.

### 4.4 Filtering & Classification Component

* **Embeddings:** OpenAI `text-embedding-ada-002` or SBERT CPU-mode.
* **Relevance:** Cosine similarity between opportunity description and user interest vectors.
* **Threshold:** Configurable (default ≥0.7).
* **Storage:** Store `vector` and `score` in `opportunities`.

### 4.5 Aggregation & Deduplication Component

* **Query:** Select opportunities where `posted_at` ≥ (now − 24 h) and `score` ≥ threshold.
* **Deduplication:** Hash `title + link`; keep highest score.
* **Ranking:** Sort by category quotas and descending score.
* **Batch Limits:** Default top 10 jobs, 5 internships, 5 scholarships, 5 research, 5 competitions/grants.

### 4.6 Notification & Scheduling Component

* **Scheduler:** Celery Beat on Heroku/Render or host cron running at 07:00 AM America/New\_York.
* **Email API:** SendGrid free tier (100 emails/day).
* **Content:** Jinja2 HTML template with sections per category; highlight deadlines.
* **Delivery:** Send to user’s email; log success/failure.

---

## 5. External Interfaces

* **OpenAI Embeddings API:** 100 k tokens/month free credits; HTTPS, API key via env var.
* **SendGrid SMTP/API:** 100 emails/day; TLS encryption.
* **Twitter Academic API:** Elevated student access; rate-limit 300 req/15 min.
* **LinkedIn RSS/API:** Unauthenticated feeds or OAuth 2.0 (subject to policy).
* **University Feeds:** RSS or JSON APIs where available.

---

## 6. Data Model

**opportunities** document example:

| Field         | Type     | Description                        |
| ------------- | -------- | ---------------------------------- |
| `_id`         | ObjectId | Unique ID                          |
| `title`       | String   | Opportunity title                  |
| `description` | String   | Full description text              |
| `deadline`    | Date     | Application deadline               |
| `category`    | String   | job, internship, scholarship, etc. |
| `link`        | String   | URL to listing                     |
| `source`      | String   | Domain or feed name                |
| `posted_at`   | DateTime | Original posting timestamp         |
| `crawled_at`  | DateTime | Timestamp when crawled             |
| `vector`      | Array    | Embedding vector                   |
| `score`       | Float    | Relevance score                    |

---

## 7. Non-Functional Requirements

* **Freshness:** 100% of delivered items ≤24 h old.
* **Availability:** 99% uptime for crawler and notifier services.
* **Performance:** Crawl ≤500 pages/day; filter ≤1000 items/hour.
* **Maintainability:** Modular codebase; configuration-driven.
* **Scalability:** Add spiders without downtime; database auto-scaling if needed.
* **Cost:** Operate within free tiers of student-pack services.

---

## 8. Deployment & Cost Constraints

| Service        | Provider        | Tier / Limits                |
| -------------- | --------------- | ---------------------------- |
| App Hosting    | Heroku / Render | Free dyno (550 h/mo)         |
| Database       | MongoDB Atlas   | 512 MB free                  |
| Embeddings     | OpenAI          | 100 k tokens/mo free credits |
| Email Delivery | SendGrid        | 100 emails/day free          |
| Scheduler      | Celery+Redis    | Render free Redis or Heroku  |

CI/CD with GitHub Actions: on push to `main`, run tests and deploy.

---

## 9. Security & Privacy

* **Credentials:** Stored as encrypted environment variables; no hard-coded secrets.
* **Transport:** TLS for all external communications (APIs, SMTP).
* **Compliance:** Honor `robots.txt`; obey site-specific terms of service.
* **Data Protection:** Sanitize HTML to prevent injection; enforce least-privilege for DB users.

---

## 10. Appendices

* **A. Sample Email Template**
* **B. Glossary**
* **C. API Quota Monitoring**
* **D. Schema Diagrams**

*End of SRS v1.0*

