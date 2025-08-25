import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Set
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse
import logging
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AtlassianScraper:
    """
    Async scraper for Atlassian Community forums
    Supports: Jira, JSM, Confluence, Rovo, and Announcements
    """
    
    BASE_URLS = {
        "jira": "https://community.atlassian.com/t5/Jira-questions/bd-p/jira-questions",
        "jsm": "https://community.atlassian.com/forums/Jira-Service-Management/ct-p/jira-service-desk", 
        "confluence": "https://community.atlassian.com/t5/Confluence-questions/bd-p/confluence-questions",
        "rovo": "https://community.atlassian.com/forums/Rovo/ct-p/rovo-atlassian-intelligence",
        "announcements": "https://community.atlassian.com/forums/Community-Announcements/gh-p/community-announcements"
    }
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.seen_urls: Set[str] = set()
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=settings.scraper_timeout)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                'User-Agent': settings.scraper_user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a single page with error handling and retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        logger.info(f"✅ Fetched {url}")
                        return content
                    else:
                        logger.warning(f"❌ HTTP {response.status} for {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout fetching {url} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"❌ Error fetching {url}: {e}")
                
            if attempt < max_retries - 1:
                await asyncio.sleep(settings.scraper_delay * (attempt + 1))
                
        return None
        
    def parse_post_list(self, html: str, base_url: str, category: str) -> List[Dict]:
        """Parse forum page to extract post links and basic info"""
        soup = BeautifulSoup(html, 'html.parser')
        posts = []
        
        # Look for post links - Atlassian uses different selectors for different page formats
        post_selectors = [
            '.lia-list-row-title a',  # New forums format - EXACT selector from HTML analysis
            'a[href*="/t5/"][href*="/td-p/"]',  # Main post links (old format)
            'a[href*="/forums/"][href*="/qaq-p/"]',  # New forums format
            '.message-subject a',  # Alternative selector
            '.thread-title a',  # Another common selector
            'a[data-testid="thread-link"]',  # New forum format
            '.lia-link-navigation',  # Generic Lithium platform links
            'article h2 a',  # Blog post titles (for announcements)
            '.post-title a',  # Blog post alternative
            'h3 a[href*="/blog/"]',  # Blog links
        ]
        
        for selector in post_selectors:
            links = soup.select(selector)
            if links:
                break
        
        for link in links[:20]:  # Limit to 20 posts per page
            try:
                href = link.get('href', '')
                if not href:
                    continue
                    
                # Make absolute URL
                full_url = urljoin(base_url, href)
                
                # Skip if already seen
                if full_url in self.seen_urls:
                    continue
                    
                self.seen_urls.add(full_url)
                
                # Extract basic info
                title = link.get_text(strip=True)
                if not title:
                    continue
                
                posts.append({
                    'url': full_url,
                    'title': title,
                    'category': category,
                    'found_at': datetime.now()
                })
                
            except Exception as e:
                logger.warning(f"Error parsing post link: {e}")
                continue
                
        logger.info(f"📋 Found {len(posts)} posts from {category} category on this page")
        return posts
        
    def find_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """Find the URL for the next page in pagination"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Common pagination selectors for Atlassian Community
        next_page_selectors = [
            'a[aria-label="Next page"]',
            'a[title="Next page"]', 
            '.lia-paging-next-page',
            '.paging-next a',
            'a.lia-link-navigation[href*="page"]',
            '.next a',
            'a:contains("Next")',
            'a[href*="/page/"]'
        ]
        
        for selector in next_page_selectors:
            next_link = soup.select_one(selector)
            if next_link and next_link.get('href'):
                next_url = urljoin(current_url, next_link.get('href'))
                logger.info(f"🔗 Found next page: {next_url}")
                return next_url
                
        # Try to find pagination with page numbers
        page_links = soup.select('a[href*="page"]')
        current_page_num = 1
        
        # Extract current page number from URL or find indicators
        if '/page/' in current_url:
            try:
                current_page_num = int(re.search(r'/page/(\d+)', current_url).group(1))
            except:
                pass
        
        # Look for next sequential page
        next_page_num = current_page_num + 1
        for link in page_links:
            href = link.get('href', '')
            if f'/page/{next_page_num}' in href or f'page={next_page_num}' in href:
                next_url = urljoin(current_url, href)
                logger.info(f"🔗 Found next page by number: {next_url}")
                return next_url
                
        return None
        
    async def scrape_post_content(self, post_url: str) -> Optional[Dict]:
        """Scrape individual post content"""
        html = await self.fetch_page(post_url)
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        try:
            # Extract title - try meta tag first, then title tag
            title = ""
            
            # Try og:title meta tag
            meta_title = soup.select_one('meta[property="og:title"]')
            if meta_title:
                title = meta_title.get('content', '').strip()
            
            # Fallback to title tag
            if not title:
                title_elem = soup.select_one('title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    # Remove "... - Atlassian Community" suffix if present
                    if ' - ' in title:
                        title = title.split(' - ')[0]
                        
            if not title:
                title = "No title"
            
            # Extract ALL posts/replies in the thread
            all_messages = []
            message_selectors = [
                '.lia-quilt-row-main .lia-message-view',  # Modern Atlassian Community messages
                '.message-list .message',  # Alternative message container
                '.thread-container .message-wrapper',  # Thread messages
                'article.message'  # Article-based messages
            ]
            
            # Try different selectors to find all messages
            messages_found = []
            for selector in message_selectors:
                messages = soup.select(selector)
                if messages:
                    messages_found = messages
                    logger.info(f"Found {len(messages)} messages using selector: {selector}")
                    break
            
            # If no messages found with specific selectors, try a more general approach
            if not messages_found:
                # Look for all message body content
                messages_found = soup.select('.lia-message-body-content')
                if messages_found:
                    logger.info(f"Found {len(messages_found)} message bodies using fallback selector")
            
            # Check for accepted solution
            has_accepted_solution = bool(soup.select_one('.lia-component-solution-info, .accepted-solution-highlight, .solution-message'))
            
            # Process each message
            for idx, msg in enumerate(messages_found[:10]):  # Limit to first 10 messages
                msg_content = ""
                msg_html = ""
                
                # Extract message content
                body = msg if msg.name == 'div' and 'lia-message-body-content' in msg.get('class', []) else msg.select_one('.lia-message-body-content, .message-body, .message-content')
                if body:
                    msg_html = str(body)
                    msg_content = body.get_text(strip=True, separator=' ')
                    
                # Check if this is an accepted solution
                is_solution = bool(msg.select_one('.lia-component-solution-info, .accepted-solution'))
                
                # Get author info
                author_elem = msg.select_one('.lia-user-name, .username, .author-name')
                author = author_elem.get_text(strip=True) if author_elem else "Unknown"
                
                # Get timestamp
                time_elem = msg.select_one('.lia-message-posted-on, .message-time, time')
                timestamp = time_elem.get_text(strip=True) if time_elem else ""
                
                all_messages.append({
                    'position': idx,
                    'author': author,
                    'content': msg_content[:1000],  # Limit individual message length
                    'html': msg_html[:5000],
                    'is_solution': is_solution,
                    'timestamp': timestamp
                })
                
                if is_solution:
                    logger.info(f"✅ Found accepted solution at position {idx}")
            
            # Combine content for storage (original post + key replies)
            if all_messages:
                # Use first message as primary content
                content = all_messages[0]['content']
                html_content = all_messages[0]['html']
                
                # Add solution or key replies to content
                solution_found = False
                for msg in all_messages[1:]:
                    if msg['is_solution']:
                        content += f"\n\n[SOLUTION by {msg['author']}]: {msg['content']}"
                        solution_found = True
                        break
                
                # If no marked solution, include first few replies
                if not solution_found and len(all_messages) > 1:
                    content += "\n\n[REPLIES]:"
                    for msg in all_messages[1:3]:  # First 2 replies
                        content += f"\n{msg['author']}: {msg['content'][:200]}..."
                
                # Store thread metadata in the post
                thread_data = {
                    'total_replies': len(all_messages) - 1,
                    'has_accepted_solution': has_accepted_solution,
                    'solution_position': next((m['position'] for m in all_messages if m['is_solution']), None),
                    'participants': list(set(m['author'] for m in all_messages))
                }
            else:
                # Fallback to original single-message extraction
                content = ""
                html_content = ""
                for selector in ['.lia-message-body-content', '.lia-message-body', '.message-body-content']:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        html_content = str(content_elem)
                        content = content_elem.get_text(strip=True, separator=' ')
                        if len(content) > 2000:
                            content = content[:2000] + "..."
                        if len(html_content) > 10000:
                            html_content = html_content[:10000] + "..."
                        break
                thread_data = {}
                    
            # Try meta description as fallback
            if not content or content == "Content not available":
                meta_desc = soup.select_one('meta[name="description"]')
                if meta_desc:
                    content = meta_desc.get('content', '').strip()
                    
            if not content:
                content = "Content not available"
            
            # Extract author using modern selectors
            author_selectors = [
                '.lia-user-name-link',  # Modern Atlassian Community
                '.MessageAuthor .username', 
                '.author-name',
                '.message-author', 
                '.username',
                '[data-author]'
            ]
            
            author = "Anonymous"
            for selector in author_selectors:
                author_elem = soup.select_one(selector)
                if author_elem:
                    author = author_elem.get_text(strip=True)
                    break
            
            # Date - try to extract post date
            date_elem = soup.select_one('[data-timestamp], .post-date, .message-date')
            post_date = datetime.now()  # Default to now if can't find date
            
            # Create excerpt (first 497 chars to allow for "...")
            if len(content) > 497:
                excerpt = content[:497] + "..."
            else:
                excerpt = content
            
            # Include thread data in the returned post
            post_data = {
                'title': title,
                'content': content,
                'html_content': html_content,
                'author': author,
                'date': post_date,
                'excerpt': excerpt,
                'thread_data': thread_data  # NEW: Full thread information
            }
            
            # Log thread analysis summary
            if thread_data:
                logger.info(f"📊 Thread analysis - Replies: {thread_data.get('total_replies', 0)}, "
                          f"Solution: {'Yes' if thread_data.get('has_accepted_solution') else 'No'}, "
                          f"Participants: {len(thread_data.get('participants', []))}")
            
            return post_data
            
        except Exception as e:
            logger.error(f"Error parsing post content from {post_url}: {e}")
            return None
            
    async def scrape_category(self, category: str, max_posts: int = 50, max_pages: int = 3) -> List[Dict]:
        """Scrape posts from a specific category across multiple pages"""
        if category not in self.BASE_URLS:
            logger.error(f"Unknown category: {category}")
            return []
            
        base_url = self.BASE_URLS[category]
        logger.info(f"🔍 Scraping {category} from {base_url} (up to {max_pages} pages)")
        
        all_post_links = []
        current_url = base_url
        page_num = 1
        
        # Scrape multiple pages
        while current_url and page_num <= max_pages and len(all_post_links) < max_posts:
            logger.info(f"📄 Fetching page {page_num} for {category}: {current_url}")
            
            # Get the forum page
            html = await self.fetch_page(current_url)
            if not html:
                logger.error(f"Failed to fetch forum page {page_num} for {category}")
                break
                
            # Parse post list from this page
            page_posts = self.parse_post_list(html, current_url, category)
            
            if not page_posts:
                logger.info(f"No posts found on page {page_num}, stopping pagination for {category}")
                break
                
            all_post_links.extend(page_posts)
            logger.info(f"📋 Collected {len(page_posts)} posts from page {page_num} (total: {len(all_post_links)})")
            
            # Look for next page
            next_url = self.find_next_page_url(html, current_url)
            if not next_url or next_url == current_url:
                logger.info(f"No more pages found for {category}")
                break
                
            current_url = next_url
            page_num += 1
            
            # Delay between pages
            await asyncio.sleep(settings.scraper_delay * 2)
        
        # Limit total posts
        all_post_links = all_post_links[:max_posts]
        logger.info(f"📊 Found {len(all_post_links)} total posts across {page_num-1} pages for {category}")
        
        # Scrape individual posts
        posts = []
        for i, post_info in enumerate(all_post_links):
            logger.info(f"📄 Scraping post {i+1}/{len(all_post_links)} from {category}")
            
            post_content = await self.scrape_post_content(post_info['url'])
            if post_content:
                # Combine info
                full_post = {
                    **post_info,
                    **post_content,
                    'url': post_info['url']  # Ensure URL is preserved
                }
                posts.append(full_post)
                
            # Rate limiting
            await asyncio.sleep(settings.scraper_delay)
            
        logger.info(f"✅ Completed scraping {len(posts)} posts from {category}")
        return posts
        
    async def scrape_all_categories(self, max_posts_per_category: int = 20, max_pages_per_category: int = 3) -> Dict[str, List[Dict]]:
        """Scrape all Atlassian community categories across multiple pages"""
        logger.info(f"🚀 Starting full community scrape ({max_posts_per_category} posts per category, up to {max_pages_per_category} pages each)")
        
        results = {}
        
        for category in self.BASE_URLS.keys():
            try:
                posts = await self.scrape_category(category, max_posts_per_category, max_pages_per_category)
                results[category] = posts
                logger.info(f"✅ {category}: {len(posts)} posts scraped")
                
                # Delay between categories
                await asyncio.sleep(settings.scraper_delay * 2)
                
            except Exception as e:
                logger.error(f"❌ Error scraping {category}: {e}")
                results[category] = []
                
        total_posts = sum(len(posts) for posts in results.values())
        logger.info(f"🎉 Scraping complete! Total posts: {total_posts}")
        
        return results
        
    def deduplicate_posts(self, posts: List[Dict]) -> List[Dict]:
        """Remove duplicate posts based on URL"""
        seen_urls = set()
        unique_posts = []
        
        for post in posts:
            url = post.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_posts.append(post)
                
        logger.info(f"🔄 Deduplicated {len(posts)} -> {len(unique_posts)} posts")
        return unique_posts
        
    async def scrape_all_forums(self, max_posts_per_forum: int = 20, max_pages_per_forum: int = 2) -> Dict[str, any]:
        """
        Scrape all forums with progress tracking - alias for scrape_all_categories
        Returns structured result for API endpoint compatibility
        """
        try:
            logger.info(f"🚀 Starting scrape of all forums (max {max_posts_per_forum} posts per forum)")
            
            # Use the existing scrape_all_categories method
            results = await self.scrape_all_categories(max_posts_per_forum, max_pages_per_forum)
            
            # Calculate totals
            total_posts = sum(len(posts) for posts in results.values())
            forums_scraped = [forum for forum, posts in results.items() if len(posts) > 0]
            
            return {
                'success': True,
                'total_forums': len(forums_scraped),
                'total_posts': total_posts,
                'forums': forums_scraped,
                'results': results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error in scrape_all_forums: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_forums': 0,
                'total_posts': 0,
                'forums': [],
                'timestamp': datetime.now().isoformat()
            }

# Async helper function for easy usage
async def scrape_atlassian_community(max_posts_per_category: int = 20, max_pages_per_category: int = 3) -> Dict[str, List[Dict]]:
    """Convenience function to scrape all categories across multiple pages"""
    async with AtlassianScraper() as scraper:
        return await scraper.scrape_all_categories(max_posts_per_category, max_pages_per_category)