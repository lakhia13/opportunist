"""
Base crawler class with common functionality for all crawlers.
"""

import asyncio
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger

from src.config import settings, TARGET_DOMAINS
from src.models.opportunity import RawPage, CrawlLog, OpportunityCreate, OpportunityCategory
from src.database.mongodb import db_manager


class BaseCrawler(ABC):
    """Base class for all crawlers with common functionality."""
    
    def __init__(self, name: str, domain: str):
        self.name = name
        self.domain = domain
        self.session: Optional[aiohttp.ClientSession] = None
        self.crawled_urls = set()
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()
    
    async def start_session(self):
        """Initialize HTTP session with proper headers."""
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        )
        logger.info(f"Started session for crawler: {self.name}")
    
    async def close_session(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            logger.info(f"Closed session for crawler: {self.name}")
    
    async def fetch_page(self, url: str, retries: int = None) -> Optional[str]:
        """Fetch a single page with retry logic."""
        if retries is None:
            retries = settings.max_retries
            
        start_time = datetime.now()
        
        for attempt in range(retries + 1):
            try:
                # Add delay between requests
                if attempt > 0:
                    await asyncio.sleep(settings.crawl_delay * attempt)
                
                async with self.session.get(url) as response:
                    response_time = (datetime.now() - start_time).total_seconds()
                    
                    if response.status == 200:
                        content = await response.text()
                        
                        # Log successful crawl
                        await self._log_crawl(
                            url=url,
                            status="success",
                            retry_count=attempt,
                            response_time=response_time
                        )
                        
                        # Store raw page
                        await self._store_raw_page(url, content, response.status, dict(response.headers))
                        
                        self.crawled_urls.add(url)
                        logger.debug(f"Successfully fetched: {url}")
                        return content
                    
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        
            except Exception as e:
                error_msg = f"Attempt {attempt + 1} failed for {url}: {str(e)}"
                logger.warning(error_msg)
                
                if attempt == retries:
                    # Log final failure
                    await self._log_crawl(
                        url=url,
                        status="failed",
                        error_message=str(e),
                        retry_count=attempt,
                        response_time=(datetime.now() - start_time).total_seconds()
                    )
        
        logger.error(f"Failed to fetch {url} after {retries + 1} attempts")
        return None
    
    async def _store_raw_page(self, url: str, content: str, status_code: int, headers: dict):
        """Store raw page data in database."""
        try:
            raw_page = RawPage(
                url=url,
                html_content=content,
                status_code=status_code,
                source_domain=self.domain,
                headers=headers
            )
            await db_manager.insert_raw_page(raw_page)
        except Exception as e:
            logger.error(f"Failed to store raw page {url}: {e}")
    
    async def _log_crawl(self, url: str, status: str, error_message: str = None, 
                        retry_count: int = 0, response_time: float = None):
        """Log crawl operation."""
        try:
            crawl_log = CrawlLog(
                url=url,
                status=status,
                error_message=error_message,
                spider_name=self.name,
                retry_count=retry_count,
                response_time=response_time
            )
            await db_manager.log_crawl(crawl_log)
        except Exception as e:
            logger.error(f"Failed to log crawl for {url}: {e}")
    
    def extract_links(self, html_content: str, base_url: str) -> List[str]:
        """Extract relevant links from HTML content."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            # Find all anchor tags
            for anchor in soup.find_all('a', href=True):
                href = anchor.get('href')
                if href:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(base_url, href)
                    
                    # Filter relevant links
                    if self._is_relevant_link(absolute_url, anchor.get_text(strip=True)):
                        links.append(absolute_url)
            
            return list(set(links))  # Remove duplicates
            
        except Exception as e:
            logger.error(f"Error extracting links from {base_url}: {e}")
            return []
    
    def _is_relevant_link(self, url: str, link_text: str) -> bool:
        """Check if a link is relevant for crawling."""
        parsed_url = urlparse(url)
        
        # Must be from the same domain
        if parsed_url.netloc != self.domain:
            return False
        
        # Skip common non-relevant patterns
        skip_patterns = [
            'javascript:', 'mailto:', 'tel:', '#',
            '.pdf', '.doc', '.docx', '.zip', '.rar',
            '/privacy', '/terms', '/contact', '/about',
            '/login', '/register', '/logout'
        ]
        
        url_lower = url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Look for relevant keywords in URL or link text
        relevant_keywords = [
            'career', 'job', 'internship', 'position', 'opportunity',
            'scholarship', 'fellowship', 'grant', 'research', 'competition',
            'apply', 'application', 'opening', 'vacancy'
        ]
        
        combined_text = f"{url} {link_text}".lower()
        return any(keyword in combined_text for keyword in relevant_keywords)
    
    def create_hash_key(self, title: str, link: str) -> str:
        """Create hash key for deduplication."""
        content = f"{title.strip().lower()}{link.strip()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    @abstractmethod
    async def extract_opportunities(self, html_content: str, source_url: str) -> List[OpportunityCreate]:
        """Extract opportunities from HTML content. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def get_entry_points(self) -> List[str]:
        """Get list of entry point URLs to start crawling. Must be implemented by subclasses."""
        pass
    
    async def crawl(self, max_pages: int = None) -> List[OpportunityCreate]:
        """Main crawling method."""
        if max_pages is None:
            max_pages = settings.max_crawl_pages
        
        logger.info(f"Starting crawl for {self.name} (max {max_pages} pages)")
        
        all_opportunities = []
        urls_to_crawl = await self.get_entry_points()
        processed_count = 0
        
        while urls_to_crawl and processed_count < max_pages:
            url = urls_to_crawl.pop(0)
            
            if url in self.crawled_urls:
                continue
            
            logger.debug(f"Crawling: {url}")
            html_content = await self.fetch_page(url)
            
            if html_content:
                try:
                    # Extract opportunities from this page
                    opportunities = await self.extract_opportunities(html_content, url)
                    all_opportunities.extend(opportunities)
                    logger.info(f"Extracted {len(opportunities)} opportunities from {url}")
                    
                    # Find more URLs to crawl
                    new_links = self.extract_links(html_content, url)
                    for link in new_links:
                        if link not in self.crawled_urls and link not in urls_to_crawl:
                            urls_to_crawl.append(link)
                    
                except Exception as e:
                    logger.error(f"Error extracting opportunities from {url}: {e}")
            
            processed_count += 1
            
            # Rate limiting
            await asyncio.sleep(settings.crawl_delay)
        
        logger.info(f"Crawl completed for {self.name}. Found {len(all_opportunities)} opportunities from {processed_count} pages")
        return all_opportunities
