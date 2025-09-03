"""
Cloud News Scraper Service
Implements functionality from getAtlassianCloudNews 1.py
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging
import re

from database import get_db, CloudNewsOperations

logger = logging.getLogger(__name__)

class CloudNewsScraper:
    """Scraper for Atlassian Cloud changes blog posts"""
    
    def __init__(self, days_to_look_back: int = 7):
        self.days_to_look_back = days_to_look_back
        self.cutoff_date = datetime.now() - timedelta(days=days_to_look_back)
        
        # Base URL pattern for cloud changes blog
        self.base_url_pattern = "https://confluence.atlassian.com/cloud/blog/{year}/{month:02d}/atlassian-cloud-changes-{date_range}-{year}"
        
        # Current week URLs to check (we'll generate these dynamically)
        self.current_urls = self._generate_current_urls()
        
    def _generate_current_urls(self) -> List[str]:
        """Generate URLs for recent Cloud changes blog posts by scraping the main blog page"""
        urls = []
        
        try:
            # First, fetch the main blog page to get current week entries
            main_blog_url = "https://confluence.atlassian.com/cloud/blog/2025"
            logger.info(f"Fetching main blog page: {main_blog_url}")
            
            html_content = self.fetch_html(main_blog_url)
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Find all links that match the pattern "atlassian-cloud-changes-"
                cloud_change_links = soup.find_all('a', href=lambda h: h and 'atlassian-cloud-changes-' in h)
                
                for link in cloud_change_links:
                    href = link.get('href', '')
                    if href.startswith('/cloud/blog/'):
                        full_url = f"https://confluence.atlassian.com{href}"
                        urls.append(full_url)
                        logger.info(f"Found current blog entry: {full_url}")
                
                logger.info(f"Found {len(urls)} current blog entries from main page")
            
        except Exception as e:
            logger.warning(f"Failed to fetch from main blog page: {e}")
        
        # Fallback: Add known working URLs if we didn't find any or as backup
        fallback_urls = [
            "https://confluence.atlassian.com/cloud/blog/2025/09/atlassian-cloud-changes-aug-25-to-sep-1-2025",
            "https://confluence.atlassian.com/cloud/blog/2025/08/atlassian-cloud-changes-aug-18-to-aug-25-2025",
            "https://confluence.atlassian.com/cloud/blog/2025/08/atlassian-cloud-changes-aug-11-to-aug-18-2025",
            "https://confluence.atlassian.com/cloud/blog/2025/08/atlassian-cloud-changes-aug-4-to-aug-11-2025",
            "https://confluence.atlassian.com/cloud/blog/2025/08/atlassian-cloud-changes-jul-28-to-aug-4-2025",
        ]
        
        # If we found URLs from the main page, prioritize recent ones and add fallbacks for backup
        if urls:
            # Sort URLs to get most recent first (newest dates)
            urls = sorted(set(urls), reverse=True)
            # Add fallbacks for additional coverage
            for fallback_url in fallback_urls:
                if fallback_url not in urls:
                    urls.append(fallback_url)
        else:
            # If main page scraping failed, use fallbacks entirely
            logger.warning("Using fallback URLs as main page scraping failed")
            urls = fallback_urls
        
        # Limit to reasonable number to avoid overwhelming the system
        urls = urls[:10]
        
        logger.info(f"Final URL list: {len(urls)} URLs to check for Cloud News")
        return urls
    
    def fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL"""
        try:
            logger.info(f"Fetching HTML content from: {url}")
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                logger.info("Successfully fetched HTML content")
                return response.text
            else:
                logger.warning(f"Failed to fetch HTML content. Status Code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching HTML from {url}: {e}")
            return None
    
    def parse_cloud_news_page(self, html_content: str, source_url: str) -> List[Dict[str, Any]]:
        """Parse a Cloud changes blog page and extract relevant features"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Create position map for maintaining order
            position_map = {}
            current_position = 0
            
            for element in soup.descendants:
                position_map[element] = current_position
                current_position += 1
            
            # Find H1 headings and panel blocks
            h1_headings = soup.find_all('h1')
            # Look for divs that contain status lozenges directly instead of restrictive class filtering
            panel_blocks = []
            
            # Find all status lozenges first
            all_lozenges = soup.find_all('span', class_=lambda c: c and 'status-macro' in c and 'aui-lozenge' in c)
            
            # Find parent divs of relevant lozenges (NEW THIS WEEK or COMING SOON)
            for lozenge in all_lozenges:
                if "NEW THIS WEEK" in lozenge.text or "COMING SOON" in lozenge.text:
                    # Find parent div containing the panel-block content
                    parent_div = lozenge.find_parent('div', class_=lambda c: c and 'panel-block' in c)
                    if parent_div and parent_div not in panel_blocks:
                        panel_blocks.append(parent_div)
            
            logger.info(f"Found {len(panel_blocks)} panel blocks")
            
            content_to_keep = []
            h1_with_updates = set()
            
            # Process panel blocks for relevant content (already filtered for relevant lozenges)
            for div in panel_blocks:
                # Determine lozenge type for this div
                lozenge_type = None
                spans = div.find_all('span', class_=lambda c: c and 'status-macro' in c and 'aui-lozenge' in c)
                
                for span in spans:
                    if "NEW THIS WEEK" in span.text:
                        lozenge_type = "NEW_THIS_WEEK"
                        break
                    elif "COMING SOON" in span.text:
                        lozenge_type = "COMING_SOON"
                        break
                
                if lozenge_type:  # Should always be true since we pre-filtered
                    # Find the closest h1 heading before this div
                    prev_h1 = div.find_previous('h1')
                    if prev_h1:
                        h1_with_updates.add(prev_h1)
                    
                    # Extract feature information
                    feature_data = self._extract_feature_data(div, lozenge_type, prev_h1, source_url)
                    if feature_data:
                        content_to_keep.append(feature_data)
            
            logger.info(f"Extracted {len(content_to_keep)} relevant features")
            return content_to_keep
            
        except Exception as e:
            logger.error(f"Error parsing cloud news page: {e}")
            return []
    
    def _extract_feature_data(self, div_element, feature_type: str, h1_element, source_url: str) -> Optional[Dict[str, Any]]:
        """Extract feature data from a panel block"""
        try:
            # Extract feature title from h4 element
            h4_element = div_element.find('h4')
            feature_title = h4_element.get_text().strip() if h4_element else "Unknown Feature"
            
            # Extract feature content
            content_div = div_element.find('div', class_='panel-block-content')
            feature_content = str(content_div) if content_div else str(div_element)
            
            # Determine product area from h1 heading
            product_area = None
            if h1_element:
                h1_text = h1_element.get_text().strip().lower()
                if 'jira' in h1_text and 'service' in h1_text:
                    product_area = 'Jira Service Management'
                elif 'jira' in h1_text:
                    product_area = 'Jira'
                elif 'confluence' in h1_text:
                    product_area = 'Confluence'
                elif 'bitbucket' in h1_text:
                    product_area = 'Bitbucket'
                elif 'trello' in h1_text:
                    product_area = 'Trello'
                elif 'atlas' in h1_text:
                    product_area = 'Atlas'
                else:
                    product_area = 'General'
            
            # Try to extract blog date from URL or page
            blog_date = self._extract_blog_date(source_url)
            
            # Extract blog title (try to find it in the page)
            blog_title = self._extract_blog_title(div_element, source_url)
            
            return {
                'source_url': source_url,
                'blog_date': blog_date,
                'blog_title': blog_title,
                'feature_title': feature_title,
                'feature_content': feature_content,
                'feature_type': feature_type,
                'product_area': product_area
            }
            
        except Exception as e:
            logger.error(f"Error extracting feature data: {e}")
            return None
    
    def _extract_blog_date(self, source_url: str) -> datetime:
        """Extract blog date from URL pattern"""
        try:
            # Extract year and month from URL pattern
            # URL format: .../cloud/blog/2025/01/atlassian-cloud-changes-...
            url_parts = source_url.split('/')
            year_index = url_parts.index('blog') + 1 if 'blog' in url_parts else -1
            
            if year_index > 0 and year_index < len(url_parts) - 1:
                year = int(url_parts[year_index])
                month = int(url_parts[year_index + 1])
                
                # Try to extract day from the date range in URL
                date_part = url_parts[-1] if url_parts else ""
                day_match = re.search(r'(\d+)', date_part)
                day = int(day_match.group(1)) if day_match else 1
                
                return datetime(year, month, day)
        except Exception as e:
            logger.error(f"Error extracting blog date from URL: {e}")
        
        # Default to current date if extraction fails
        return datetime.now()
    
    def _extract_blog_title(self, div_element, source_url: str) -> str:
        """Extract blog title from page or generate from URL"""
        try:
            # Try to find title in the page structure
            page_soup = div_element.find_parent('html') if div_element else None
            if page_soup:
                title_element = page_soup.find('title')
                if title_element:
                    return title_element.get_text().strip()
            
            # Generate title from URL if not found
            url_parts = source_url.split('/')
            if url_parts:
                last_part = url_parts[-1]
                # Convert URL slug to readable title
                title = last_part.replace('-', ' ').title()
                return title
        except Exception as e:
            logger.error(f"Error extracting blog title: {e}")
        
        return "Atlassian Cloud Changes"
    
    async def scrape_cloud_news(self) -> List[Dict[str, Any]]:
        """Scrape cloud news from multiple recent blog posts"""
        all_features = []
        
        try:
            logger.info("Starting cloud news scraping...")
            
            for url in self.current_urls:
                try:
                    html_content = self.fetch_html(url)
                    if html_content:
                        features = self.parse_cloud_news_page(html_content, url)
                        all_features.extend(features)
                        logger.info(f"Found {len(features)} features from {url}")
                except Exception as e:
                    logger.error(f"Error processing URL {url}: {e}")
                    continue
            
            logger.info(f"Cloud news scraping complete. Found {len(all_features)} total features")
            return all_features
            
        except Exception as e:
            logger.error(f"Error during cloud news scraping: {e}")
            return []
    
    async def store_cloud_news(self, scraped_features: List[Dict[str, Any]]) -> int:
        """Store scraped cloud news in database"""
        stored_count = 0
        
        try:
            with next(get_db()) as db:
                for feature_data in scraped_features:
                    try:
                        # Store in database using get_or_create to avoid duplicates
                        CloudNewsOperations.get_or_create_cloud_news(db, feature_data)
                        stored_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error storing cloud news feature: {e}")
        
        except Exception as e:
            logger.error(f"Error storing cloud news: {e}")
        
        logger.info(f"Stored {stored_count} cloud news features in database")
        return stored_count
    
    async def run_full_scrape(self) -> Dict[str, Any]:
        """Run complete cloud news scraping and storage"""
        try:
            logger.info("Starting full cloud news scrape...")
            
            # Scrape all data
            scraped_features = await self.scrape_cloud_news()
            
            # Store in database
            stored_count = await self.store_cloud_news(scraped_features)
            
            result = {
                'success': True,
                'features_found': len(scraped_features),
                'total_stored': stored_count,
                'scrape_date': datetime.now().isoformat(),
                'urls_processed': len(self.current_urls)
            }
            
            logger.info(f"Cloud news scrape completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error during full cloud news scrape: {e}")
            return {
                'success': False,
                'error': str(e),
                'scrape_date': datetime.now().isoformat()
            }
    
    def get_recent_cloud_news_summary(self) -> Dict[str, Any]:
        """Get summary of recent cloud news from database"""
        try:
            with next(get_db()) as db:
                stats = CloudNewsOperations.get_cloud_news_stats(db, self.days_to_look_back)
                return {
                    'success': True,
                    'summary': stats
                }
        except Exception as e:
            logger.error(f"Error getting cloud news summary: {e}")
            return {
                'success': False,
                'error': str(e)
            }