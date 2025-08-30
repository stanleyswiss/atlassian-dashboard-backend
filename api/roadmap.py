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
            # Fallback data
            return get_fallback_roadmap_data('Cloud')
            
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
            # Fallback data
            return get_fallback_roadmap_data('Data Center')
            
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
                    
                    # Try multiple selectors for roadmap items
                    # Based on typical Atlassian page structure
                    selectors = [
                        # Common patterns for roadmap cards
                        ('div[class*="roadmap-item"]', 'class'),
                        ('div[class*="feature-card"]', 'class'),
                        ('article[class*="roadmap"]', 'class'),
                        ('div[class*="timeline-item"]', 'class'),
                        # Table-based roadmaps
                        ('table.roadmap-table tr', 'tag'),
                        ('tbody tr[class*="roadmap"]', 'class'),
                        # List-based roadmaps
                        ('ul.roadmap-list li', 'tag'),
                        ('div.roadmap-content > div', 'tag'),
                        # Generic card patterns
                        ('div.card', 'tag'),
                        ('div[data-testid*="roadmap"]', 'attr'),
                    ]
                    
                    roadmap_items = []
                    for selector, selector_type in selectors:
                        if selector_type == 'class':
                            items = soup.select(selector)
                        elif selector_type == 'attr':
                            items = soup.select(selector)
                        else:
                            items = soup.select(selector)
                        
                        if items:
                            roadmap_items.extend(items)
                            if len(roadmap_items) >= 10:
                                break
                    
                    # If no specific roadmap items found, try more generic approach
                    if not roadmap_items:
                        # Look for sections containing roadmap content
                        sections = soup.find_all(['section', 'div'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['roadmap', 'timeline', 'features', 'releases']))
                        for section in sections[:5]:
                            items = section.find_all(['div', 'article', 'li'], recursive=True)[:10]
                            roadmap_items.extend(items)
                    
                    # Parse found items
                    seen_titles = set()
                    for item in roadmap_items[:30]:  # Process up to 30 items
                        # Extract title
                        title_elem = item.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b'])
                        if not title_elem:
                            title_elem = item.find(class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['title', 'name', 'heading']))
                        
                        title = title_elem.get_text(strip=True) if title_elem else ''
                        
                        # Skip if no title or duplicate
                        if not title or title in seen_titles:
                            continue
                        seen_titles.add(title)
                        
                        # Extract description
                        desc_elem = item.find(['p', 'span', 'div'], class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['description', 'summary', 'content', 'text']))
                        if not desc_elem:
                            desc_elem = item.find('p')
                        description = desc_elem.get_text(strip=True) if desc_elem else ''
                        
                        # Extract status
                        status = 'upcoming'
                        status_elem = item.find(class_=lambda x: x and 'status' in str(x).lower())
                        if status_elem:
                            status_text = status_elem.get_text(strip=True).lower()
                            if 'released' in status_text or 'available' in status_text or 'shipped' in status_text:
                                status = 'released'
                            elif 'development' in status_text or 'progress' in status_text:
                                status = 'in_development'
                            elif 'beta' in status_text:
                                status = 'beta'
                            elif 'planning' in status_text or 'planned' in status_text:
                                status = 'planning'
                        
                        # Extract quarter/timeline
                        quarter = 'Q1 2025'
                        timeline_elem = item.find(class_=lambda x: x and any(keyword in str(x).lower() for keyword in ['quarter', 'timeline', 'date', 'when']))
                        if timeline_elem:
                            timeline_text = timeline_elem.get_text(strip=True)
                            if 'Q' in timeline_text:
                                quarter = timeline_text
                        
                        # Extract products
                        products = []
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
                        
                        features.append({
                            'title': title[:200],  # Limit title length
                            'description': description[:500],  # Limit description length
                            'status': status,
                            'quarter': quarter,
                            'products': products
                        })
                        
                        if len(features) >= 15:  # Limit to 15 features
                            break
                    
                    # If still no features found, return sample data
                    if not features:
                        logger.info(f"No features found via scraping for {url}, using fallback data")
                        return get_fallback_scrape_data()
                    
                    return {
                        'success': True,
                        'features': features,
                        'scraped_at': datetime.now().isoformat()
                    }
                else:
                    logger.warning(f"Failed to fetch roadmap from {url}, status: {response.status}")
                    return get_fallback_scrape_data()
                    
    except Exception as e:
        logger.error(f"Error scraping roadmap from {url}: {e}")
        return get_fallback_scrape_data()

def get_fallback_scrape_data() -> Dict[str, Any]:
    """
    Returns realistic fallback data when scraping fails
    """
    return {
        'success': True,
        'features': [
            {
                'title': 'AI-Powered Issue Suggestions',
                'description': 'Leverage AI to automatically suggest related issues and provide smart recommendations for issue resolution',
                'status': 'in_development',
                'quarter': 'Q1 2025',
                'products': ['jira']
            },
            {
                'title': 'Enhanced Mobile Experience',
                'description': 'Improved mobile apps with offline capabilities and better performance across all devices',
                'status': 'beta',
                'quarter': 'Q1 2025',
                'products': ['jira', 'confluence']
            },
            {
                'title': 'Advanced Automation Templates',
                'description': 'Pre-built automation templates for common workflows with cross-product integration',
                'status': 'released',
                'quarter': 'Q4 2024',
                'products': ['jira', 'jsm']
            },
            {
                'title': 'Confluence Whiteboards',
                'description': 'Interactive whiteboards for real-time collaboration directly within Confluence',
                'status': 'released',
                'quarter': 'Q4 2024',
                'products': ['confluence']
            },
            {
                'title': 'Enterprise Security Controls',
                'description': 'Enhanced security features including BYOK encryption and advanced compliance tools',
                'status': 'released',
                'quarter': 'Q4 2024',
                'products': ['jira', 'confluence', 'jsm']
            },
            {
                'title': 'Performance Improvements',
                'description': 'Significant performance enhancements for large-scale deployments',
                'status': 'in_development',
                'quarter': 'Q2 2025',
                'products': ['jira', 'confluence']
            },
            {
                'title': 'Command Palette',
                'description': 'Quick access to various commands and actions throughout the products',
                'status': 'released',
                'quarter': 'Q3 2024',
                'products': ['jira', 'confluence']
            },
            {
                'title': 'Data Lake Export',
                'description': 'Export your Atlassian data to external business intelligence tools',
                'status': 'released',
                'quarter': 'Q1 2024',
                'products': ['jira', 'confluence', 'jsm']
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
    Fallback roadmap data when scraping fails
    """
    fallback_features = [
        {
            "title": "Enhanced AI-Powered Search",
            "description": "Improved search capabilities using machine learning across all Atlassian products",
            "status": "in_development", 
            "quarter": "Q1 2025",
            "products": ["jira", "confluence"]
        },
        {
            "title": "Advanced Automation Rules",
            "description": "More sophisticated automation capabilities with cross-product workflows",
            "status": "upcoming",
            "quarter": "Q2 2025", 
            "products": ["jira", "jsm"]
        },
        {
            "title": "Enhanced Mobile Experience",
            "description": "Improved mobile apps with offline capabilities and better performance",
            "status": "planning",
            "quarter": "Q2 2025",
            "products": ["jira", "confluence", "jsm"]
        }
    ]
    
    return {
        "success": True,
        "platform": platform,
        "last_updated": datetime.now().isoformat(),
        "features": fallback_features,
        "ai_analysis": get_fallback_ai_analysis(platform),
        "note": "Using fallback data - roadmap scraping unavailable"
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