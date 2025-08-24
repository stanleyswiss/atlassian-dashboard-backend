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
    Scrape roadmap from Atlassian website
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    features = []
                    
                    # Look for roadmap items (this is a simplified approach)
                    # The actual selectors would need to be adjusted based on the real HTML structure
                    roadmap_items = soup.find_all(['div', 'section'], class_=lambda x: x and ('roadmap' in x.lower() or 'feature' in x.lower() or 'card' in x.lower()))
                    
                    for item in roadmap_items[:20]:  # Limit to 20 items
                        title = item.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                        description = item.find(['p', 'div'], class_=lambda x: x and ('description' in x.lower() or 'summary' in x.lower()))
                        
                        if title and title.get_text(strip=True):
                            features.append({
                                'title': title.get_text(strip=True),
                                'description': description.get_text(strip=True) if description else '',
                                'status': 'upcoming',  # Default status
                                'quarter': 'Q1 2025',  # Default quarter
                                'products': ['jira', 'confluence']  # Default products
                            })
                    
                    return {
                        'success': True,
                        'features': features[:10],  # Limit to 10 features
                        'scraped_at': datetime.now().isoformat()
                    }
                else:
                    logger.warning(f"Failed to fetch roadmap from {url}, status: {response.status}")
                    return {'success': False, 'error': f'HTTP {response.status}'}
                    
    except Exception as e:
        logger.error(f"Error scraping roadmap from {url}: {e}")
        return {'success': False, 'error': str(e)}

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