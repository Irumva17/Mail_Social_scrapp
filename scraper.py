import asyncio
import aiohttp
import re
import csv
import json
import logging
import time
import random
from urllib.parse import urljoin, urlparse
from typing import List, Set, Dict, Optional
from aiohttp_socks import ProxyConnector

from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)

# Configuration
class Config:
    MAX_CONCURRENCY = 50  # Adjust based on CPU/Bandwidth
    TIMEOUT = 15  # Seconds
    MAX_RETRIES = 3
    DEEP_CRAWL_KEYWORDS = ['contact', 'about', 'legal', 'privacy', 'terms']
    OUTPUT_FILE = 'results.jsonl'
    PROXY_FILE = 'proxies.txt'  # Optional: Path to proxy file (protocol://ip:port)
    USER_AGENT_FALLBACK = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class AsyncScraper:
    def __init__(self, urls: List[str], use_proxies: bool = False):
        self.urls = self.normalize_urls(urls)
        self.use_proxies = use_proxies
        self.proxies = self.load_proxies() if use_proxies else []
        self.ua = UserAgent(fallback=Config.USER_AGENT_FALLBACK)
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENCY)
        
        # Regex Patterns
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        self.social_patterns = {
            'linkedin': re.compile(r'linkedin\.com/(?:in|company)/[\w-]+'),
            'twitter': re.compile(r'(?:twitter\.com|x\.com)/[\w]+'),
            'facebook': re.compile(r'facebook\.com/[\w.]+'),
            'instagram': re.compile(r'instagram\.com/[\w.]+'),
            'youtube': re.compile(r'youtube\.com/(?:channel/|user/|c/|@)[\w-]+'),
            'tiktok': re.compile(r'tiktok\.com/@[\w.-]+'),
            'threads': re.compile(r'threads\.net/@[\w.-]+'),
            'pinterest': re.compile(r'pinterest\.com/[\w.-]+'),
            'snapchat': re.compile(r'snapchat\.com/add/[\w.-]+'),
            'telegram': re.compile(r't\.me/[\w]+'),
            'whatsapp': re.compile(r'wa\.me/[\d]+')
        }

    def normalize_urls(self, urls: List[str]) -> List[str]:
        cleaned = []
        for url in urls:
            if not url.startswith('http'):
                url = 'https://' + url
            cleaned.append(url)
        return list(set(cleaned))

    def load_proxies(self) -> List[str]:
        try:
            with open(Config.PROXY_FILE, 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            logger.warning(f"{Fore.YELLOW}Proxy file not found. Running without proxies.")
            return []

    def get_random_headers(self) -> Dict[str, str]:
        return {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def get_proxy(self) -> Optional[str]:
        if self.proxies:
            return random.choice(self.proxies)
        return None

    async def fetch(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        retries = 0
        while retries < Config.MAX_RETRIES:
            try:
                proxy = self.get_proxy()
                async with session.get(
                    url, 
                    headers=self.get_random_headers(), 
                    proxy=proxy, 
                    timeout=Config.TIMEOUT,
                    ssl=False 
                ) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429: # Too Many Requests
                        wait_time = (2 ** retries) + random.uniform(0, 1)
                        logger.warning(f"{Fore.RED}429 at {url}. Retrying in {wait_time:.2f}s...")
                        await asyncio.sleep(wait_time)
                    elif response.status >= 500:
                        retries += 1
                        await asyncio.sleep(1)
                    else:
                        # Non-recoverable error (404, 403, etc.)
                        return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.debug(f"Error fetching {url}: {e}")
                retries += 1
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e}")
                return None
        
        return None

    async def parse(self, html: str, url: str) -> Dict:
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        emails = set(self.email_pattern.findall(text))
        
        socials = {}
        for platform, pattern in self.social_patterns.items():
            # Search in hrefs specifically for better accuracy
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if pattern.search(href):
                    links.append(href)
            if links:
                socials[platform] = list(set(links))

        return {
            'emails': list(emails),
            'socials': socials,
            'deep_links': self.extract_deep_links(soup, url)
        }

    def extract_deep_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        deep_links = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if any(kw in href for kw in Config.DEEP_CRAWL_KEYWORDS):
                full_url = urljoin(base_url, a['href'])
                # Ensure we stay on the same domain
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    deep_links.add(full_url)
        return list(deep_links)

    async def process_url(self, session: aiohttp.ClientSession, url: str):
        async with self.semaphore:
            logger.info(f"{Fore.CYAN}Scraping: {url}")
            html = await self.fetch(session, url)
            
            result_data = {
                'url': url,
                'emails': [],
                'socials': {},
                'status': 'failed'
            }

            if html:
                parsed = await self.parse(html, url)
                result_data['emails'].extend(parsed['emails'])
                result_data['socials'].update(parsed['socials'])
                result_data['status'] = 'success' # Partial success at least

                # Deep Crawl
                deep_links = parsed['deep_links']
                if deep_links:
                    logger.info(f"{Fore.BLUE}Deep crawling {len(deep_links)} links for {url}")
                    # We create tasks for deep links but limit them to avoid recursion hell. 
                    # Just one level of depth for now efficiently.
                    deep_tasks = [self.fetch(session, link) for link in deep_links[:3]] # limit to top 3 relevant links
                    deep_responses = await asyncio.gather(*deep_tasks)
                    
                    for d_html in deep_responses:
                        if d_html:
                            d_parsed = await self.parse(d_html, url) # Parse as if it's the same site
                            result_data['emails'].extend(d_parsed['emails'])
                            for k, v in d_parsed['socials'].items():
                                if k not in result_data['socials']:
                                    result_data['socials'][k] = []
                                result_data['socials'][k].extend(v)

                # Clean up duplicates
                result_data['emails'] = list(set(result_data['emails']))
                for k in result_data['socials']:
                    result_data['socials'][k] = list(set(result_data['socials'][k]))

            await self.save_data(result_data)

    async def save_data(self, data: Dict):
        # Asynchronous file writing (blocking but fast enough for this scale, can use aiofiles if strict)
        try:
            with open(Config.OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    async def run(self):
        # Connector for better performance
        connector = aiohttp.TCPConnector(limit=Config.MAX_CONCURRENCY + 10, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [self.process_url(session, url) for url in self.urls]
            await asyncio.gather(*tasks)

if __name__ == "__main__":
    # Example Usage
    print(f"{Fore.GREEN}Starting High-Performance Scraper...")
    
    # Ideally load from a file or arguments
    target_urls = [
       "example.com",
       # Add more targets here
    ]
    
    # If a file is provided as an argument, read it
    import sys
    if len(sys.argv) > 1:
         with open(sys.argv[1], 'r') as f:
             target_urls = [line.strip() for line in f if line.strip()]

    if not target_urls:
         print(f"{Fore.RED}No targets found. Please provide a file with URLs.")
         # creating a dummy list for demonstration if run without args
         target_urls = ["https://www.google.com/contact", "https://kigaliux.com"]

    scraper = AsyncScraper(target_urls, use_proxies=False)
    
    start_time = time.time()
    try:
        asyncio.run(scraper.run())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Scraping interrupted by user.")
    
    duration = time.time() - start_time
    print(f"{Fore.GREEN}Completed in {duration:.2f} seconds.")
