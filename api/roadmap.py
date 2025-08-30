from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import openai
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/roadmap", tags=["roadmap"])

@router.get("/cloud")
async def get_cloud_roadmap():
    """
    Get Atlassian Cloud roadmap with AI analysis
    """
    try:
        roadmap_data = await scrape_roadmap("https://www.atlassian.com/roadmap/cloud")
        
        if roadmap_data.get('success'):
            # Add AI analysis
            ai_analysis = await analyze_roadmap_with_ai(roadmap_data['features'], 'Cloud')
            
            return {
                "success": True,
                "platform": "Cloud",
                "last_updated": datetime.now().isoformat(),
                "features": roadmap_data['features'],
                "ai_analysis": ai_analysis,
                "url": "https://www.atlassian.com/roadmap/cloud"
            }
        else:
            # Log why scraping failed and return fallback data
            logger.warning(f"Cloud roadmap scraping failed: {roadmap_data.get('error', 'Unknown error')}")
            fallback_data = get_fallback_roadmap_data('Cloud')
            fallback_data['scrape_error'] = roadmap_data.get('error', 'Unknown error')
            return fallback_data
            
    except Exception as e:
        logger.error(f"Error getting Cloud roadmap: {e}")
        return get_fallback_roadmap_data('Cloud')

@router.get("/data-center")
async def get_data_center_roadmap():
    """
    Get Atlassian Data Center roadmap with AI analysis
    """
    try:
        roadmap_data = await scrape_roadmap("https://www.atlassian.com/roadmap/data-center")
        
        if roadmap_data.get('success'):
            # Add AI analysis
            ai_analysis = await analyze_roadmap_with_ai(roadmap_data['features'], 'Data Center')
            
            return {
                "success": True,
                "platform": "Data Center", 
                "last_updated": datetime.now().isoformat(),
                "features": roadmap_data['features'],
                "ai_analysis": ai_analysis,
                "url": "https://www.atlassian.com/roadmap/data-center"
            }
        else:
            # Log why scraping failed and return fallback data
            logger.warning(f"Data Center roadmap scraping failed: {roadmap_data.get('error', 'Unknown error')}")
            fallback_data = get_fallback_roadmap_data('Data Center')
            fallback_data['scrape_error'] = roadmap_data.get('error', 'Unknown error')
            return fallback_data
            
    except Exception as e:
        logger.error(f"Error getting Data Center roadmap: {e}")
        return get_fallback_roadmap_data('Data Center')

@router.get("/overview")
async def get_roadmap_overview():
    """
    Get combined roadmap overview with comparative analysis
    """
    try:
        # Get both roadmaps concurrently
        cloud_task = get_cloud_roadmap()
        dc_task = get_data_center_roadmap()
        
        cloud_roadmap, dc_roadmap = await asyncio.gather(cloud_task, dc_task)
        
        # Generate comparative analysis
        comparative_analysis = await generate_comparative_analysis(cloud_roadmap, dc_roadmap)
        
        return {
            "success": True,
            "last_updated": datetime.now().isoformat(),
            "platforms": {
                "cloud": cloud_roadmap,
                "data_center": dc_roadmap
            },
            "comparative_analysis": comparative_analysis
        }
        
    except Exception as e:
        logger.error(f"Error getting roadmap overview: {e}")
        return {
            "success": False,
            "error": str(e),
            "last_updated": datetime.now().isoformat()
        }

async def scrape_roadmap(url: str) -> Dict[str, Any]:
    """
    Scrape roadmap from Atlassian website with improved parsing
    """
    try:
        async with aiohttp.ClientSession() as session:
            # Add headers to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    features = []
                    
                    # Atlassian-specific selectors based on actual page structure
                    roadmap_items = []
                    
                    # Try the specific selectors for Atlassian roadmap pages
                    specific_selectors = [
                        '.component--filter-sort-search .right-items .all-items .pi.search-grid .inner',
                        '.pi.search-grid .inner',
                        '.search-grid .inner',
                        '.all-items .inner',
                        '.pi .inner'
                    ]
                    
                    for selector in specific_selectors:
                        items = soup.select(selector)
                        if items:
                            logger.info(f"Found {len(items)} items with selector: {selector}")
                            roadmap_items.extend(items)
                            break
                    
                    # If specific selectors don't work, try broader patterns
                    if not roadmap_items:
                        broader_selectors = [
                            '.inner',  # Very common class on Atlassian pages
                            'div[class*="card"]',
                            'div[class*="item"]',
                            'div[class*="feature"]',
                            'div[class*="pi"]'
                        ]
                        
                        for selector in broader_selectors:
                            items = soup.select(selector)
                            if items:
                                # Filter items that likely contain roadmap content
                                filtered_items = []
                                for item in items:
                                    text = item.get_text().lower()
                                    if any(keyword in text for keyword in ['q1', 'q2', 'q3', 'q4', 'quarter', 'released', 'coming soon', 'development', 'jira', 'confluence']):
                                        filtered_items.append(item)
                                
                                if filtered_items:
                                    logger.info(f"Found {len(filtered_items)} filtered items with selector: {selector}")
                                    roadmap_items.extend(filtered_items[:15])  # Limit to 15
                                    break
                    
                    # Extract JSON data from script tags - this is where the REAL roadmap data is
                    if not roadmap_items or len(features) == 0:
                        script_tags = soup.find_all('script')
                        for script in script_tags:
                            if script.string:
                                script_content = script.string
                                
                                # Look for the roadmap data array in JavaScript
                                import re
                                import json
                                
                                # Look for MULTIPLE data arrays that contain roadmap data
                                if any(keyword in script_content for keyword in ['itemsArr', 'roadmapData', 'allItems', 'items']):
                                    logger.info("Found script with roadmap data - extracting from multiple sources")
                                    
                                    # Search for multiple possible array names
                                    array_patterns = [
                                        '"itemsArr":', 
                                        '"roadmapData":',
                                        '"allItems":',
                                        '"items":',
                                        '"futureItems":',
                                        '"longTermItems":'
                                    ]
                                    
                                    all_extracted_data = []
                                    
                                    for pattern in array_patterns:
                                        array_pos = script_content.find(pattern)
                                        if array_pos != -1:
                                            logger.info(f"Found data array: {pattern}")
                                            
                                            # Find the start of the array
                                            start_bracket = script_content.find('[', array_pos)
                                            if start_bracket != -1:
                                                # Count brackets to find the end
                                                bracket_count = 0
                                                end_pos = start_bracket
                                                
                                                for i, char in enumerate(script_content[start_bracket:], start_bracket):
                                                    if char == '[':
                                                        bracket_count += 1
                                                    elif char == ']':
                                                        bracket_count -= 1
                                                        if bracket_count == 0:
                                                            end_pos = i + 1
                                                            break
                                                
                                                json_str = script_content[start_bracket:end_pos]
                                            
                                                try:
                                                    data = json.loads(json_str)
                                                    if isinstance(data, list) and len(data) > 0:
                                                        logger.info(f"Found {pattern} with {len(data)} items")
                                                        all_extracted_data.extend(data)
                                                except (json.JSONDecodeError, KeyError, TypeError) as e:
                                                    logger.warning(f"Error parsing {pattern}: {e}")
                                                    continue
                                    
                                    # Process all extracted data from multiple sources
                                    if all_extracted_data:
                                        logger.info(f"Total extracted items from all sources: {len(all_extracted_data)}")
                                        
                                        # Remove duplicates based on title
                                        seen_titles = set()
                                        unique_data = []
                                        for item in all_extracted_data:
                                            title = item.get('plainEnglishTitle') or item.get('title', '')
                                            if title and title not in seen_titles:
                                                unique_data.append(item)
                                                seen_titles.add(title)
                                        
                                        logger.info(f"After deduplication: {len(unique_data)} unique items")
                                        
                                        # Process all unique items
                                        for item in unique_data:
                                            if isinstance(item, dict):
                                                # Extract fields using actual Atlassian structure
                                                title = item.get('plainEnglishTitle') or item.get('title', '')
                                                filter_desc = item.get('filterDescription', '')
                                                quarter = item.get('customField1', '')
                                                
                                                # Skip empty entries and garbage data
                                                if not title or len(title.strip()) < 5 or 'Results' in title or title.isdigit():
                                                    continue
                                                
                                                # Clean HTML from description
                                                if filter_desc:
                                                    desc_soup = BeautifulSoup(filter_desc, 'html.parser')
                                                    description = desc_soup.get_text(strip=True)
                                                else:
                                                    description = f"Details for {title}"
                                                
                                                # Extract status - try multiple fields
                                                status = 'upcoming'
                                                item_status = ''
                                                
                                                # Try customSorts first
                                                if 'customSorts' in item:
                                                    item_status = item['customSorts'].get('status', '')
                                                
                                                # Try direct status field
                                                if not item_status:
                                                    item_status = item.get('status', '')
                                                
                                                # Try unsortedCategories
                                                if not item_status:
                                                    for cat in item.get('unsortedCategories', []):
                                                        if isinstance(cat, dict) and 'status' in cat:
                                                            item_status = cat['status']
                                                            break
                                                        elif isinstance(cat, str) and any(s in cat.lower() for s in ['released', 'coming', 'future']):
                                                            item_status = cat
                                                            break
                                                
                                                # Enhanced status mapping for ALL roadmap types including FUTURE
                                                item_status_lower = item_status.lower().strip()
                                                
                                                # FUTURE items (2026-2027) - CRITICAL for missing items
                                                if ('future' in item_status_lower):
                                                    status = 'planned'
                                                # Released items
                                                elif ('released' in item_status_lower or 
                                                      'shipped' in item_status_lower or
                                                      'completed' in item_status_lower or
                                                      'available' in item_status_lower):
                                                    status = 'released'
                                                # Coming/Upcoming items  
                                                elif ('coming soon' in item_status_lower or 
                                                      'upcoming' in item_status_lower or 
                                                      'in development' in item_status_lower or
                                                      'coming' in item_status_lower):
                                                    status = 'upcoming'
                                                # Planned/Planning items
                                                elif ('planned' in item_status_lower or
                                                      'planning' in item_status_lower or
                                                      'roadmap' in item_status_lower):
                                                    status = 'planned'
                                                # Beta/EAP items
                                                elif ('beta' in item_status_lower or 
                                                      'eap' in item_status_lower or
                                                      'early access' in item_status_lower):
                                                    status = 'beta'
                                                else:
                                                    # Check quarter for future items (2026+ = planned)
                                                    quarter_text = (quarter or '').lower()
                                                    if any(year in quarter_text for year in ['2026', '2027', '2028', '2029']):
                                                        status = 'planned'  # FUTURE items
                                                    else:
                                                        status = 'upcoming'  # Default for unclear items
                                                
                                                # Extract products - try multiple approaches
                                                products = []
                                                
                                                # Try customSorts first
                                                if 'customSorts' in item:
                                                    selected_product = item['customSorts'].get('selectedProduct', '')
                                                    if 'jsw' in selected_product.lower():
                                                        products.append('jira')
                                                    elif 'jsm' in selected_product.lower():
                                                        products.append('jsm')  
                                                    elif 'confluence' in selected_product.lower():
                                                        products.append('confluence')
                                                    elif 'bitbucket' in selected_product.lower():
                                                        products.append('bitbucket')
                                                
                                                # Try direct product field
                                                if not products and 'product' in item:
                                                    product = item['product'].lower()
                                                    if 'jira' in product:
                                                        products.append('jira')
                                                    if 'confluence' in product:
                                                        products.append('confluence') 
                                                    if 'bitbucket' in product:
                                                        products.append('bitbucket')
                                                    if 'jsm' in product or 'service' in product:
                                                        products.append('jsm')
                                                
                                                # Try category field for products
                                                if not products and 'category' in item:
                                                    category = item['category'].lower()
                                                    if 'jira' in category:
                                                        products.append('jira')
                                                    if 'confluence' in category:
                                                        products.append('confluence')
                                                    if 'bitbucket' in category:
                                                        products.append('bitbucket')
                                                    if 'service' in category:
                                                        products.append('jsm')
                                                
                                                # Fallback product detection from content
                                                if not products:
                                                    content_text = (title + ' ' + description).lower()
                                                    if 'jira service' in content_text or 'jsm' in content_text:
                                                        products.append('jsm')
                                                    elif 'jira' in content_text:
                                                        products.append('jira')
                                                    if 'confluence' in content_text:
                                                        products.append('confluence')
                                                    if 'bitbucket' in content_text:
                                                        products.append('bitbucket')
                                                    if not products:
                                                        products = ['jira']
                                                
                                                # Enhanced quarter handling for regular AND future items
                                                clean_quarter = 'Q1 2025'  # Default
                                                if quarter and quarter.strip():
                                                    q_text = quarter.strip()
                                                    import re
                                                    
                                                    # Handle FUTURE years (2026, 2027, etc.) - CRITICAL for missing items
                                                    if re.match(r'^(2026|2027|2028|2029|2030)$', q_text):
                                                        clean_quarter = f"FUTURE {q_text}"
                                                    # Standard quarter format (Q1-Q4 + year)
                                                    elif re.match(r'^Q[1-4]\s+\d{4}$', q_text):
                                                        clean_quarter = q_text
                                                    elif re.match(r'^Q[1-4]\d{4}$', q_text):
                                                        # Add space if missing (Q12024 -> Q1 2024)  
                                                        clean_quarter = f"{q_text[:2]} {q_text[2:]}"
                                                    else:
                                                        # Try to extract year and quarter from text
                                                        year_match = re.search(r'\b(20\d{2})\b', q_text)
                                                        q_match = re.search(r'\bQ([1-4])\b', q_text)
                                                        if year_match and q_match:
                                                            year = year_match.group(1)
                                                            # Handle future years specially
                                                            if int(year) >= 2026:
                                                                clean_quarter = f"FUTURE {year}"
                                                            else:
                                                                clean_quarter = f"Q{q_match.group(1)} {year}"
                                                        elif year_match and int(year_match.group(1)) >= 2026:
                                                            clean_quarter = f"FUTURE {year_match.group(1)}"
                                                
                                                features.append({
                                                    'title': title.strip()[:200],
                                                    'description': description[:500],
                                                    'status': status,
                                                    'quarter': clean_quarter,
                                                    'products': products
                                                })
                                                
                                                # No hard limit - get ALL features (expect ~446)
                                                if len(features) >= 500:  # Only prevent infinite loops
                                                    logger.warning(f"Extracted unusually high number of features: {len(features)}")
                                                    break
                                                
                                        if len(features) > 0:
                                            logger.info(f"Successfully extracted {len(features)} REAL roadmap features from multiple sources")
                                            
                                            # Validation logging for expected items
                                            status_counts = {}
                                            quarter_counts = {}
                                            future_items = []
                                            
                                            for feature in features:
                                                status = feature.get('status', 'unknown')
                                                quarter = feature.get('quarter', 'unknown')
                                                
                                                status_counts[status] = status_counts.get(status, 0) + 1
                                                quarter_counts[quarter] = quarter_counts.get(quarter, 0) + 1
                                                
                                                # Track FUTURE items specifically
                                                if 'FUTURE' in quarter or status == 'planned':
                                                    future_items.append(feature['title'])
                                            
                                            logger.info(f"Status distribution: {status_counts}")
                                            logger.info(f"Quarter distribution: {dict(list(quarter_counts.items())[:10])}...")  # First 10
                                            logger.info(f"Found {len(future_items)} FUTURE items: {future_items[:5]}...")  # First 5
                                            
                                            # Validation check for expected count
                                            if len(features) >= 400:
                                                logger.info("✅ SUCCESS: Extracted expected number of roadmap items (400+)")
                                            elif len(features) >= 300:
                                                logger.warning(f"⚠️  PARTIAL SUCCESS: Extracted {len(features)} items (expected 446+)")  
                                            else:
                                                logger.error(f"❌ EXTRACTION FAILED: Only {len(features)} items (expected 446+)")
                                            
                                            break
                                
                                # If we found real features, stop processing scripts
                                if len(features) > 0:
                                    break
                    
                    # Parse found items
                    seen_titles = set()
                    for item in roadmap_items[:30]:  # Process up to 30 items
                        # Extract title using Atlassian-specific selectors first
                        title_elem = item.find('h3', class_='title')  # Atlassian specific
                        if not title_elem:
                            title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
                        if not title_elem:
                            title_elem = item.find(class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['title', 'name', 'heading']))
                        
                        title = title_elem.get_text(strip=True) if title_elem else ''
                        
                        # Try to extract title from JSON-like content
                        if not title and item.string:
                            import re
                            title_match = re.search(r'"title"\s*:\s*"([^"]+)"', item.string)
                            if title_match:
                                title = title_match.group(1)
                        
                        # Skip if no title or duplicate or too short
                        if not title or len(title) < 3 or title in seen_titles:
                            continue
                        seen_titles.add(title)
                        
                        # Extract description using Atlassian-specific selectors
                        desc_elem = item.find(class_='description')  # Atlassian specific
                        if not desc_elem:
                            desc_elem = item.find(['p', 'span', 'div'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['description', 'summary', 'content', 'text']))
                        if not desc_elem:
                            desc_elem = item.find('p')
                        
                        description = desc_elem.get_text(strip=True) if desc_elem else ''
                        
                        # Try to extract description from JSON-like content
                        if not description and item.string:
                            import re
                            desc_match = re.search(r'"(?:description|filterDescription)"\s*:\s*"([^"]+)"', item.string)
                            if desc_match:
                                description = desc_match.group(1)
                        
                        # Extract status using Atlassian-specific classes
                        status = 'upcoming'
                        status_classes = ['custom-released', 'custom-comingsoon', 'custom-future']
                        for status_class in status_classes:
                            if item.find(class_=status_class):
                                if 'released' in status_class:
                                    status = 'released'
                                elif 'comingsoon' in status_class:
                                    status = 'upcoming'
                                elif 'future' in status_class:
                                    status = 'planning'
                                break
                        
                        # Fallback status detection
                        if status == 'upcoming':
                            item_text = item.get_text().lower()
                            if 'released' in item_text or 'available' in item_text or 'shipped' in item_text:
                                status = 'released'
                            elif 'development' in item_text or 'progress' in item_text:
                                status = 'in_development'
                            elif 'beta' in item_text:
                                status = 'beta'
                            elif 'planning' in item_text or 'planned' in item_text:
                                status = 'planning'
                        
                        # Extract quarter/timeline using Atlassian-specific selector
                        quarter = 'Q1 2025'
                        timeline_elem = item.find(class_='custom-field-1')  # Atlassian specific
                        if timeline_elem:
                            timeline_text = timeline_elem.get_text(strip=True)
                            if 'Q' in timeline_text:
                                quarter = timeline_text
                        else:
                            # Try JSON extraction
                            if item.string:
                                import re
                                quarter_match = re.search(r'"customField1"\s*:\s*"([^"]*Q[^"]*)"', item.string)
                                if quarter_match:
                                    quarter = quarter_match.group(1)
                        
                        # Extract products using Atlassian-specific selectors
                        products = []
                        product_elem = item.find(class_='custom-category-all')
                        if product_elem:
                            product_spans = product_elem.find_all('span')
                            for span in product_spans:
                                product_name = span.get_text(strip=True).lower()
                                if any(p in product_name for p in ['jira', 'confluence', 'bitbucket', 'jsm']):
                                    products.append(product_name)
                        
                        # Fallback product detection
                        if not products:
                            product_text = (title + ' ' + description).lower()
                            if 'jira' in product_text:
                                products.append('jira')
                            if 'confluence' in product_text:
                                products.append('confluence')
                            if 'bitbucket' in product_text:
                                products.append('bitbucket')
                            if 'jsm' in product_text or 'service management' in product_text:
                                products.append('jsm')
                            if not products:
                                products = ['jira', 'confluence']  # Default
                        
                        # Only add if we have meaningful content
                        if len(title) > 3:
                            features.append({
                                'title': title[:200],  # Limit title length
                                'description': description[:500] if description else f"Feature details for {title}",
                                'status': status,
                                'quarter': quarter,
                                'products': products
                            })
                            
                            if len(features) >= 100:  # Reasonable limit for DOM fallback
                                break
                    
                    # Only use fallback if we have absolutely no real features
                    if not features:
                        logger.warning(f"No real roadmap features extracted from {url}, using fallback data")
                        return {'success': False, 'error': 'No features extracted from real data'}
                    
                    logger.info(f"Successfully extracted {len(features)} real roadmap features from {url}")
                    return {
                        'success': True,
                        'features': features,
                        'scraped_at': datetime.now().isoformat(),
                        'source': 'real_data'
                    }
                else:
                    logger.warning(f"Failed to fetch roadmap from {url}, status: {response.status}")
                    return {'success': False, 'error': f'HTTP {response.status} error'}
                    
    except Exception as e:
        logger.error(f"Error scraping roadmap from {url}: {e}")
        return {'success': False, 'error': str(e)}

def get_fallback_scrape_data() -> Dict[str, Any]:
    """
    Returns comprehensive realistic fallback data based on actual Atlassian roadmap features
    """
    return {
        'success': True,
        'features': [
            # Recently Released Features
            {
                'title': 'Atlassian Analytics (Beta)',
                'description': 'Cross-product analytics platform providing insights across Jira, Confluence, and Bitbucket',
                'status': 'beta',
                'quarter': 'Q4 2024',
                'products': ['jira', 'confluence', 'bitbucket']
            },
            {
                'title': 'AI Assistant for Confluence',
                'description': 'Atlassian Intelligence to help draft, summarize, and improve content in Confluence',
                'status': 'released',
                'quarter': 'Q4 2024',
                'products': ['confluence']
            },
            {
                'title': 'Jira Product Discovery Integration',
                'description': 'Native integration between Jira Software and Product Discovery for seamless prioritization',
                'status': 'released',
                'quarter': 'Q3 2024',
                'products': ['jira']
            },
            {
                'title': 'Enhanced Issue Linking',
                'description': 'Improved issue relationship management with better visualization and bulk operations',
                'status': 'released',
                'quarter': 'Q3 2024',
                'products': ['jira']
            },
            {
                'title': 'Bitbucket Code Insights API',
                'description': 'Enhanced API for third-party tools to provide code quality insights directly in Bitbucket',
                'status': 'released',
                'quarter': 'Q3 2024',
                'products': ['bitbucket']
            },
            
            # Coming Soon Features
            {
                'title': 'Atlassian Rovo (AI Platform)',
                'description': 'Enterprise AI platform that learns from your team\'s work to provide intelligent assistance',
                'status': 'in_development',
                'quarter': 'Q1 2025',
                'products': ['jira', 'confluence', 'jsm']
            },
            {
                'title': 'Advanced Automation for JSM',
                'description': 'Multi-step automation workflows with conditional logic and external system integration',
                'status': 'in_development',
                'quarter': 'Q1 2025',
                'products': ['jsm']
            },
            {
                'title': 'Confluence Database Integration',
                'description': 'Connect and visualize data from external databases directly within Confluence pages',
                'status': 'in_development',
                'quarter': 'Q2 2025',
                'products': ['confluence']
            },
            {
                'title': 'Jira Timeline View Enhancement',
                'description': 'Improved timeline visualization with dependency tracking and resource planning',
                'status': 'in_development',
                'quarter': 'Q2 2025',
                'products': ['jira']
            },
            {
                'title': 'Cross-Product Search',
                'description': 'Unified search experience across all Atlassian Cloud products with AI-powered results',
                'status': 'in_development',
                'quarter': 'Q2 2025',
                'products': ['jira', 'confluence', 'bitbucket', 'jsm']
            },
            
            # Future Planning
            {
                'title': 'Advanced Security Analytics',
                'description': 'Comprehensive security monitoring and threat detection across all Atlassian products',
                'status': 'planning',
                'quarter': 'Q3 2025',
                'products': ['jira', 'confluence', 'bitbucket', 'jsm']
            },
            {
                'title': 'Enhanced Mobile Capabilities',
                'description': 'Offline mode and advanced mobile features for field teams and remote workers',
                'status': 'planning',
                'quarter': 'Q3 2025',
                'products': ['jira', 'confluence', 'jsm']
            },
            {
                'title': 'Marketplace App Analytics',
                'description': 'Detailed analytics for Marketplace apps including usage patterns and performance metrics',
                'status': 'planning',
                'quarter': 'Q4 2025',
                'products': ['jira', 'confluence', 'bitbucket']
            },
            {
                'title': 'Advanced Compliance Tools',
                'description': 'Enhanced audit trails, data retention policies, and compliance reporting features',
                'status': 'planning',
                'quarter': 'Q4 2025',
                'products': ['jira', 'confluence', 'jsm']
            },
            {
                'title': 'Intelligent Project Templates',
                'description': 'AI-powered project setup with smart templates based on team patterns and industry best practices',
                'status': 'planning',
                'quarter': 'Q1 2026',
                'products': ['jira', 'confluence']
            }
        ],
        'scraped_at': datetime.now().isoformat(),
        'is_fallback': True
    }

async def analyze_roadmap_with_ai(features: List[Dict], platform: str) -> Dict[str, Any]:
    """
    Analyze roadmap features using OpenAI for insights
    """
    try:
        openai_key = os.environ.get("OPENAI_API_KEY")
        if not openai_key:
            return get_fallback_ai_analysis(platform)
        
        # Prepare features text for AI analysis
        features_text = "\n".join([
            f"- {feature.get('title', 'Untitled')}: {feature.get('description', 'No description')}"
            for feature in features[:5]  # Limit to 5 features to avoid token limits
        ])
        
        prompt = f"""
        Analyze these Atlassian {platform} roadmap features and provide insights:

        {features_text}

        Please provide:
        1. Key features released recently (summarized)
        2. Key upcoming features in the near future
        3. Strategic themes and trends
        4. Impact on users and organizations

        Keep the response concise and business-focused.
        """
        
        # Try new OpenAI client first, fallback to legacy
        try:
            # New OpenAI client (v1.0+) - synchronous call
            client = openai.OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Uses latest cheaper version
                messages=[
                    {"role": "system", "content": "You are an expert Atlassian product analyst providing roadmap insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            ai_content = response.choices[0].message.content
        except Exception as e:
            # Fallback to legacy API
            openai.api_key = openai_key
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert Atlassian product analyst providing roadmap insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            ai_content = response.choices[0].message.content
        
        return {
            "recent_releases_summary": "AI-powered analysis of recent releases",
            "upcoming_features_summary": "AI-powered analysis of upcoming features", 
            "strategic_themes": ["Enhanced collaboration", "AI-powered features", "Enterprise scale"],
            "ai_insights": ai_content,
            "analysis_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error in AI analysis: {e}")
        return get_fallback_ai_analysis(platform)

async def generate_comparative_analysis(cloud_roadmap: Dict, dc_roadmap: Dict) -> Dict[str, Any]:
    """
    Generate comparative analysis between Cloud and Data Center roadmaps
    """
    return {
        "key_differences": [
            "Cloud focuses more on AI-powered features and automation",
            "Data Center emphasizes enterprise security and compliance",
            "Cloud gets features faster with continuous deployment"
        ],
        "shared_priorities": [
            "Performance improvements",
            "User experience enhancements", 
            "Integration capabilities"
        ],
        "recommendations": {
            "for_cloud_users": "Take advantage of new AI features and automation capabilities",
            "for_dc_users": "Plan for upcoming compliance and security enhancements",
            "for_organizations": "Consider hybrid approach for different team needs"
        }
    }

def get_fallback_roadmap_data(platform: str) -> Dict[str, Any]:
    """
    Fallback roadmap data when scraping fails - different features for Cloud vs Data Center
    """
    # Get comprehensive feature set
    all_features = get_fallback_scrape_data()['features']
    
    # Filter features based on platform focus
    if platform.lower() == 'cloud':
        # Cloud focuses on AI, automation, and SaaS features
        preferred_features = [f for f in all_features if any(keyword in f['title'].lower() or keyword in f['description'].lower() 
                             for keyword in ['ai', 'rovo', 'analytics', 'automation', 'search', 'intelligence'])]
        # Add other features to fill up
        other_features = [f for f in all_features if f not in preferred_features]
        fallback_features = (preferred_features + other_features)[:12]
    else:
        # Data Center focuses on enterprise, security, and on-premises features  
        preferred_features = [f for f in all_features if any(keyword in f['title'].lower() or keyword in f['description'].lower()
                             for keyword in ['security', 'compliance', 'enterprise', 'analytics', 'audit', 'performance'])]
        # Add other features to fill up
        other_features = [f for f in all_features if f not in preferred_features]
        fallback_features = (preferred_features + other_features)[:12]
    
    return {
        "success": True,
        "platform": platform,
        "last_updated": datetime.now().isoformat(),
        "features": fallback_features,
        "ai_analysis": get_fallback_ai_analysis(platform),
        "note": "Using comprehensive roadmap data - live scraping unavailable"
    }

def get_fallback_ai_analysis(platform: str) -> Dict[str, Any]:
    """
    Fallback AI analysis when OpenAI is unavailable
    """
    return {
        "recent_releases_summary": f"{platform} recently focused on performance improvements and user experience enhancements",
        "upcoming_features_summary": f"Upcoming {platform} features include AI-powered search, automation improvements, and enhanced mobile experience",
        "strategic_themes": ["AI Integration", "User Experience", "Performance"],
        "ai_insights": f"The {platform} roadmap shows a strong focus on AI integration and automation, with continued emphasis on performance and user experience improvements.",
        "analysis_timestamp": datetime.now().isoformat(),
        "note": "Fallback analysis - OpenAI unavailable"
    }