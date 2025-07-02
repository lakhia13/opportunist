"""
Crawler for company career pages.
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger
import dateparser

from src.crawlers.base_crawler import BaseCrawler
from src.models.opportunity import OpportunityCreate, OpportunityCategory
from src.config import TARGET_DOMAINS


class CompanyCrawler(BaseCrawler):
    """Crawler for company career pages."""
    
    def __init__(self, domain: str):
        super().__init__(f"company_{domain.replace('.', '_')}", domain)
        self.career_patterns = [
            '/careers', '/jobs', '/positions', '/opportunities',
            '/work-with-us', '/join-us', '/hiring'
        ]
    
    async def get_entry_points(self) -> List[str]:
        """Get career page entry points for the company."""
        entry_points = []
        base_url = f"https://{self.domain}"
        
        # Try common career page patterns
        for pattern in self.career_patterns:
            entry_points.append(f"{base_url}{pattern}")
        
        # Add root domain to find career links
        entry_points.append(base_url)
        
        return entry_points
    
    async def extract_opportunities(self, html_content: str, source_url: str) -> List[OpportunityCreate]:
        """Extract job opportunities from company career pages."""
        opportunities = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try different common patterns for job listings
            job_containers = self._find_job_containers(soup)
            
            for container in job_containers:
                opportunity = await self._extract_opportunity_from_container(container, source_url)
                if opportunity:
                    opportunities.append(opportunity)
            
        except Exception as e:
            logger.error(f"Error extracting opportunities from {source_url}: {e}")
        
        return opportunities
    
    def _find_job_containers(self, soup: BeautifulSoup) -> List:
        """Find containers that likely contain job information."""
        containers = []
        
        # Common selectors for job listings
        job_selectors = [
            # Common class names
            '[class*="job"]', '[class*="career"]', '[class*="position"]',
            '[class*="opening"]', '[class*="opportunity"]', '[class*="listing"]',
            
            # Common data attributes
            '[data-job]', '[data-position]', '[data-role]',
            
            # Semantic HTML
            'article', '.role', '.position-item', '.job-item',
            
            # Popular job board classes
            '.lever-job', '.greenhouse-job', '.workday-job',
            '.job-posting', '.job-card', '.career-item'
        ]
        
        for selector in job_selectors:
            try:
                found_containers = soup.select(selector)
                containers.extend(found_containers)
            except Exception:
                continue
        
        # If no specific containers found, try finding divs with job-related text
        if not containers:
            containers = self._find_containers_by_content(soup)
        
        return containers
    
    def _find_containers_by_content(self, soup: BeautifulSoup) -> List:
        """Find containers by looking for job-related content."""
        containers = []
        job_keywords = ['software', 'engineer', 'developer', 'intern', 'manager', 'analyst', 'specialist']
        
        # Look for divs, articles, sections with job-related content
        for tag in soup.find_all(['div', 'article', 'section', 'li']):
            text_content = tag.get_text().strip().lower()
            if any(keyword in text_content for keyword in job_keywords) and len(text_content) > 20:
                containers.append(tag)
        
        return containers[:50]  # Limit to avoid processing too many
    
    async def _extract_opportunity_from_container(self, container, source_url: str) -> Optional[OpportunityCreate]:
        """Extract opportunity details from a container element."""
        try:
            # Extract title
            title = self._extract_title(container)
            if not title or len(title.strip()) < 3:
                return None
            
            # Extract description
            description = self._extract_description(container)
            
            # Extract link
            link = self._extract_link(container, source_url)
            if not link:
                link = source_url
            
            # Extract deadline (if available)
            deadline = self._extract_deadline(container)
            
            # Determine category
            category = self._determine_category(title, description)
            
            # Extract posted date (if available)
            posted_at = self._extract_posted_date(container)
            
            # Create opportunity
            opportunity = OpportunityCreate(
                title=title.strip(),
                description=description.strip(),
                deadline=deadline,
                category=category,
                link=link,
                source=self.domain,
                posted_at=posted_at or datetime.utcnow()
            )
            
            return opportunity
            
        except Exception as e:
            logger.debug(f"Error extracting opportunity from container: {e}")
            return None
    
    def _extract_title(self, container) -> Optional[str]:
        """Extract job title from container."""
        # Try different title selectors
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            '.title', '.job-title', '.position-title', '.role-title',
            '[class*="title"]', '[class*="heading"]',
            'a[href]', '.job-link', '[data-title]'
        ]
        
        for selector in title_selectors:
            try:
                element = container.select_one(selector)
                if element:
                    text = element.get_text().strip()
                    if text and len(text) > 2:
                        return text
            except Exception:
                continue
        
        # Fallback: use container text if it's short enough
        container_text = container.get_text().strip()
        if container_text and len(container_text) < 200:
            # Take first line as title
            first_line = container_text.split('\n')[0].strip()
            if len(first_line) > 2:
                return first_line
        
        return None
    
    def _extract_description(self, container) -> str:
        """Extract job description from container."""
        # Try to find description in common places
        desc_selectors = [
            '.description', '.job-description', '.summary',
            '.content', '.details', '[class*="desc"]',
            'p', '.text'
        ]
        
        description_parts = []
        
        for selector in desc_selectors:
            try:
                elements = container.select(selector)
                for element in elements:
                    text = element.get_text().strip()
                    if text and len(text) > 10:
                        description_parts.append(text)
            except Exception:
                continue
        
        if description_parts:
            return ' '.join(description_parts)[:2000]  # Limit length
        
        # Fallback: use container text
        container_text = container.get_text().strip()
        return container_text[:2000] if container_text else "No description available"
    
    def _extract_link(self, container, source_url: str) -> Optional[str]:
        """Extract job application link."""
        # Look for links within the container
        link_elements = container.find_all('a', href=True)
        
        for link_elem in link_elements:
            href = link_elem.get('href')
            if href:
                # Convert relative to absolute URL
                absolute_url = urljoin(source_url, href)
                
                # Check if this looks like a job link
                link_text = link_elem.get_text().strip().lower()
                link_href = href.lower()
                
                # Skip obvious non-job links
                skip_patterns = ['privacy', 'terms', 'contact', 'about', 'home', 'mailto:', 'tel:']
                if any(pattern in link_href for pattern in skip_patterns):
                    continue
                
                # Prefer links with job-related text or URLs
                job_indicators = ['apply', 'view', 'details', 'job', 'position', 'role']
                if any(indicator in link_text or indicator in link_href for indicator in job_indicators):
                    return absolute_url
                
                # Return first valid link as fallback
                if not any(pattern in link_href for pattern in skip_patterns):
                    return absolute_url
        
        return None
    
    def _extract_deadline(self, container) -> Optional[datetime]:
        """Extract application deadline if available."""
        text = container.get_text()
        
        # Look for deadline patterns
        deadline_patterns = [
            r'deadline[:\s]+([^\n]+)',
            r'apply by[:\s]+([^\n]+)',
            r'due[:\s]+([^\n]+)',
            r'expires?[:\s]+([^\n]+)',
            r'closes?[:\s]+([^\n]+)'
        ]
        
        for pattern in deadline_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    parsed_date = dateparser.parse(date_str)
                    if parsed_date and parsed_date > datetime.now():
                        return parsed_date
                except Exception:
                    continue
        
        return None
    
    def _extract_posted_date(self, container) -> Optional[datetime]:
        """Extract when the job was posted."""
        text = container.get_text()
        
        # Look for posted date patterns
        posted_patterns = [
            r'posted[:\s]+([^\n]+)',
            r'published[:\s]+([^\n]+)',
            r'listed[:\s]+([^\n]+)',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        for pattern in posted_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                try:
                    parsed_date = dateparser.parse(date_str)
                    if parsed_date and parsed_date <= datetime.now():
                        return parsed_date
                except Exception:
                    continue
        
        # Default to current time if no date found
        return datetime.utcnow()
    
    def _determine_category(self, title: str, description: str) -> OpportunityCategory:
        """Determine the category of the opportunity based on title and description."""
        text = f"{title} {description}".lower()
        
        # Check for internship keywords
        internship_keywords = ['intern', 'internship', 'summer program', 'co-op', 'coop']
        if any(keyword in text for keyword in internship_keywords):
            return OpportunityCategory.INTERNSHIP
        
        # Check for research keywords
        research_keywords = ['research', 'phd', 'postdoc', 'researcher', 'scientist']
        if any(keyword in text for keyword in research_keywords):
            return OpportunityCategory.RESEARCH
        
        # Default to job
        return OpportunityCategory.JOB


class CompanyCrawlerManager:
    """Manager for running multiple company crawlers."""
    
    def __init__(self):
        self.crawlers = {}
        self._initialize_crawlers()
    
    def _initialize_crawlers(self):
        """Initialize crawlers for all target company domains."""
        for domain in TARGET_DOMAINS.get("companies", []):
            self.crawlers[domain] = CompanyCrawler(domain)
    
    async def crawl_all(self, max_pages_per_domain: int = 50) -> List[OpportunityCreate]:
        """Crawl all company domains."""
        all_opportunities = []
        
        for domain, crawler in self.crawlers.items():
            try:
                logger.info(f"Starting crawl for company: {domain}")
                async with crawler:
                    opportunities = await crawler.crawl(max_pages_per_domain)
                    all_opportunities.extend(opportunities)
                    logger.info(f"Completed crawl for {domain}: {len(opportunities)} opportunities")
            except Exception as e:
                logger.error(f"Error crawling {domain}: {e}")
        
        return all_opportunities
    
    async def crawl_domain(self, domain: str, max_pages: int = 50) -> List[OpportunityCreate]:
        """Crawl a specific domain."""
        if domain not in self.crawlers:
            self.crawlers[domain] = CompanyCrawler(domain)
        
        crawler = self.crawlers[domain]
        async with crawler:
            return await crawler.crawl(max_pages)
