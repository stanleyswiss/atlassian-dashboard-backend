"""
Vision AI service for analyzing screenshots and images from Atlassian Community posts
Extracts issues, error messages, configurations, and solutions from visual content
"""
import asyncio
import logging
import re
import aiohttp
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import openai
import os
from config import settings

logger = logging.getLogger(__name__)

class VisionAnalyzer:
    """
    AI service for analyzing images and screenshots from community posts
    """
    
    def __init__(self, api_key: str = None):
        # Get API key from multiple sources
        self.api_key = (
            api_key or 
            settings.openai_api_key or 
            os.environ.get("OPENAI_API_KEY") or 
            os.getenv("OPENAI_API_KEY")
        )
        
        logger.info(f"🔑 VisionAnalyzer - API key available: {bool(self.api_key)}")
        
        if self.api_key:
            try:
                # Try new OpenAI client (v1.0+)
                self.openai_client = openai.OpenAI(api_key=self.api_key)
                logger.info("✅ OpenAI v1.0+ client initialized for vision analysis")
            except Exception as e:
                # Fallback to legacy method
                openai.api_key = self.api_key
                self.openai_client = None
                logger.info("✅ OpenAI legacy client initialized for vision analysis")
        else:
            logger.warning("❌ No OpenAI API key found for vision analysis")
            self.openai_client = None
            
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def extract_images_from_post(self, post_html: str, post_url: str = "") -> List[str]:
        """
        Extract image URLs from forum post HTML content
        """
        try:
            soup = BeautifulSoup(post_html, 'html.parser')
            image_urls = []
            
            # Common image selectors in Atlassian Community
            image_selectors = [
                'img[src]',  # All images
                '.lia-image-message img',  # Embedded images
                '.lia-video-message img',  # Video thumbnails  
                '.message-body img',  # Message content images
                'a[href$=".png"], a[href$=".jpg"], a[href$=".jpeg"], a[href$=".gif"]',  # Image links
                '.attachment-image img',  # Attachments
                '.embedded-image img'  # Embedded content
            ]
            
            for selector in image_selectors:
                elements = soup.select(selector)
                for element in elements:
                    # Get image URL from src or href
                    img_url = element.get('src') or element.get('href')
                    if img_url:
                        # Make absolute URL if needed
                        if post_url and not img_url.startswith('http'):
                            img_url = urljoin(post_url, img_url)
                        
                        # Filter out tiny icons and avatars
                        if self._is_screenshot_image(img_url, element):
                            image_urls.append(img_url)
            
            # Remove duplicates while preserving order
            unique_images = []
            seen = set()
            for url in image_urls:
                if url not in seen:
                    unique_images.append(url)
                    seen.add(url)
            
            logger.info(f"🖼️ Found {len(unique_images)} screenshot images in post")
            return unique_images[:5]  # Limit to 5 images per post
            
        except Exception as e:
            logger.error(f"Error extracting images from post: {e}")
            return []
    
    def _is_screenshot_image(self, img_url: str, img_element) -> bool:
        """
        Determine if an image is likely a meaningful screenshot vs icon/avatar
        """
        # Skip obvious non-screenshots
        skip_patterns = [
            'avatar', 'profile', 'icon', 'logo', 'badge', 'rank',
            'emoji', 'smiley', 'star', 'thumb', 'vote', 'flag'
        ]
        
        url_lower = img_url.lower()
        for pattern in skip_patterns:
            if pattern in url_lower:
                return False
        
        # Check image dimensions if available
        width = img_element.get('width')
        height = img_element.get('height')
        
        if width and height:
            try:
                w, h = int(width), int(height)
                # Skip very small images (likely icons)
                if w < 100 or h < 100:
                    return False
                # Prefer larger images (likely screenshots)
                if w > 300 and h > 200:
                    return True
            except:
                pass
        
        # Check for screenshot-like file naming
        screenshot_indicators = [
            'screenshot', 'image', 'screen', 'capture', 'snap',
            'error', 'dialog', 'config', 'setup', 'workflow'
        ]
        
        for indicator in screenshot_indicators:
            if indicator in url_lower:
                return True
        
        # Default to including if unsure
        return True
    
    async def analyze_screenshot(self, image_url: str, post_context: str = "") -> Dict[str, Any]:
        """
        Analyze a single screenshot using OpenAI Vision API
        """
        try:
            if not self.api_key:
                logger.warning(f"🚫 No API key available for vision analysis of {image_url}")
                return self._generate_mock_vision_analysis(image_url)
            
            logger.info(f"🤖 Making real OpenAI Vision API call for image: {image_url}")
            
            # Download and analyze image
            prompt = self._create_vision_analysis_prompt(post_context)
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]
            
            try:
                if self.openai_client:
                    # New OpenAI client (v1.0+) - synchronous call
                    logger.info("Using OpenAI v1.0+ client for vision analysis (synchronous)")
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",  # Now supports vision and much cheaper
                        messages=messages,
                        max_tokens=800,
                        temperature=0.2
                    )
                    content = response.choices[0].message.content
                    tokens = response.usage.total_tokens
                else:
                    # Legacy OpenAI API
                    logger.info("Using OpenAI legacy API for vision analysis")
                    response = await openai.ChatCompletion.acreate(
                        model="gpt-4o-mini",  # Use same model for consistency
                        messages=messages,
                        max_tokens=800,
                        temperature=0.2
                    )
                    content = response.choices[0].message.content
                    tokens = response.usage.total_tokens if hasattr(response, 'usage') else 'unknown'
                
                logger.info(f"✅ OpenAI Vision API call successful, tokens: {tokens}")
                
            except Exception as api_error:
                logger.error(f"OpenAI Vision API call failed: {api_error}")
                raise api_error
            
            # Parse response
            analysis_data = self._parse_vision_response(content)
            
            return {
                "image_url": image_url,
                "analysis_successful": True,
                **analysis_data
            }
            
        except Exception as e:
            logger.error(f"Vision analysis failed for {image_url}: {e}")
            return {
                "image_url": image_url,
                "analysis_successful": False,
                "error": str(e),
                **self._generate_mock_vision_analysis(image_url)
            }
    
    def _create_vision_analysis_prompt(self, post_context: str) -> str:
        """
        Create a detailed prompt for vision analysis
        """
        return f"""
        Analyze this screenshot from an Atlassian Community forum post and extract actionable information.

        Post context: {post_context[:500]}

        Please identify and return JSON with:

        1. **content_type**: What type of content is shown (error_dialog, configuration_screen, workflow_setup, dashboard_view, code_snippet, documentation, success_message, other)

        2. **extracted_issues**: List of specific problems, errors, or issues visible in the image
        
        3. **error_messages**: Any error text, codes, or warning messages shown
        
        4. **atlassian_products**: Which Atlassian products are visible (jira, confluence, jsm, bitbucket, bamboo, rovo, other)
        
        5. **configuration_details**: Any settings, configurations, or setup steps shown
        
        6. **problem_severity**: How critical does this issue appear (critical, high, medium, low, none)
        
        7. **resolution_hints**: Any solutions, workarounds, or fixes visible in the image
        
        8. **business_impact**: Potential business impact (productivity_loss, data_access_blocked, workflow_broken, feature_unavailable, minor_inconvenience, none)
        
        9. **actionable_summary**: 1-2 sentence summary of what action needs to be taken based on what's shown

        Focus on technical details that would help Atlassian product teams understand and address user problems.
        If the image is not clear or doesn't show technical content, indicate that in content_type as "unclear" or "non_technical".
        """
    
    def _parse_vision_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse OpenAI vision response into structured data
        """
        try:
            import json
            # Try to extract JSON from response
            if '{' in response_text and '}' in response_text:
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                json_text = response_text[json_start:json_end]
                return json.loads(json_text)
        except:
            pass
        
        # Fallback parsing if JSON extraction fails
        return {
            "content_type": "unclear",
            "extracted_issues": [],
            "error_messages": [],
            "atlassian_products": [],
            "configuration_details": [],
            "problem_severity": "unknown",
            "resolution_hints": [],
            "business_impact": "unknown",
            "actionable_summary": response_text[:200] if response_text else "Analysis unavailable",
            "raw_response": response_text
        }
    
    async def batch_analyze_images(self, posts_with_images: List[Dict]) -> List[Dict]:
        """
        Analyze images from multiple posts efficiently
        """
        results = []
        batch_size = getattr(settings, 'vision_analysis_batch_size', 5)
        
        for i in range(0, len(posts_with_images), batch_size):
            batch = posts_with_images[i:i + batch_size]
            batch_tasks = []
            
            for post in batch:
                images = post.get('images', [])
                post_context = f"Title: {post.get('title', '')}\nContent: {post.get('content', '')[:300]}"
                
                for image_url in images:
                    task = self.analyze_screenshot(image_url, post_context)
                    batch_tasks.append({
                        'task': task,
                        'post_id': post.get('id'),
                        'image_url': image_url
                    })
            
            # Execute batch
            logger.info(f"🔍 Analyzing batch {i//batch_size + 1}: {len(batch_tasks)} images")
            
            for task_info in batch_tasks:
                try:
                    analysis = await task_info['task']
                    results.append({
                        'post_id': task_info['post_id'],
                        'image_url': task_info['image_url'],
                        'analysis': analysis
                    })
                except Exception as e:
                    logger.error(f"Batch analysis failed for image: {e}")
                    results.append({
                        'post_id': task_info['post_id'],
                        'image_url': task_info['image_url'],
                        'analysis': {'error': str(e), 'analysis_successful': False}
                    })
            
            # Rate limiting between batches
            if i + batch_size < len(posts_with_images):
                await asyncio.sleep(2)
        
        logger.info(f"✅ Completed vision analysis for {len(results)} images")
        return results
    
    async def analyze_post_with_vision(self, post: Dict) -> Dict[str, Any]:
        """
        Analyze a single post including both text and visual content
        """
        try:
            # Extract images from post - use html_content if available, fallback to content
            post_html = post.get('html_content') or post.get('content', '')
            post_url = post.get('url', '')
            
            # Debug logging for image extraction
            img_tags_count = len(re.findall(r'<img[^>]*>', post_html.lower())) if post_html else 0
            src_count = len(re.findall(r'src\s*=\s*["\'][^"\']*["\']', post_html.lower())) if post_html else 0
            
            logger.info(f"🔍 Image extraction debug - Post {post.get('id', 'unknown')}: "
                       f"HTML content: {'Yes' if post.get('html_content') else 'No'}, "
                       f"HTML length: {len(post_html)}, "
                       f"<img> tags: {img_tags_count}, "
                       f"src= attributes: {src_count}")
            
            images = await self.extract_images_from_post(post_html, post_url)
            
            if not images:
                return {
                    "has_images": False,
                    "vision_analysis": None,
                    "enhanced_category": await self._analyze_text_only(post)
                }
            
            # Analyze each image
            vision_results = []
            post_context = f"Title: {post.get('title', '')}\nContent: {post.get('content', '')[:500]}"
            
            for image_url in images:
                analysis = await self.analyze_screenshot(image_url, post_context)
                if analysis.get('analysis_successful'):
                    vision_results.append(analysis)
            
            # Combine vision insights
            combined_analysis = self._combine_vision_insights(vision_results)
            
            return {
                "has_images": True,
                "image_count": len(images),
                "vision_analysis": combined_analysis,
                "enhanced_category": self._categorize_with_vision(post, combined_analysis)
            }
            
        except Exception as e:
            logger.error(f"Error in post vision analysis: {e}")
            return {
                "has_images": False,
                "vision_analysis": None,
                "enhanced_category": "uncategorized",
                "error": str(e)
            }
    
    def _combine_vision_insights(self, vision_results: List[Dict]) -> Dict[str, Any]:
        """
        Combine insights from multiple images in a single post
        """
        if not vision_results:
            return {}
        
        # Aggregate data from all images
        all_issues = []
        all_errors = []
        all_products = set()
        highest_severity = "none"
        all_impacts = []
        
        severity_order = ["none", "low", "medium", "high", "critical"]
        
        for result in vision_results:
            all_issues.extend(result.get('extracted_issues', []))
            all_errors.extend(result.get('error_messages', []))
            all_products.update(result.get('atlassian_products', []))
            all_impacts.append(result.get('business_impact', 'none'))
            
            # Track highest severity
            current_severity = result.get('problem_severity', 'none')
            if severity_order.index(current_severity) > severity_order.index(highest_severity):
                highest_severity = current_severity
        
        return {
            "content_type": vision_results[0].get('content_type', 'mixed'),
            "extracted_issues": list(set(all_issues)),  # Remove duplicates
            "error_messages": list(set(all_errors)),
            "atlassian_products": list(all_products),
            "problem_severity": highest_severity,
            "business_impact": self._determine_highest_impact(all_impacts),
            "image_count": len(vision_results),
            "actionable_summary": self._create_combined_summary(vision_results)
        }
    
    def _determine_highest_impact(self, impacts: List[str]) -> str:
        """Determine the highest business impact from multiple assessments"""
        impact_order = ["none", "minor_inconvenience", "feature_unavailable", "workflow_broken", "data_access_blocked", "productivity_loss"]
        
        highest = "none"
        for impact in impacts:
            if impact in impact_order and impact_order.index(impact) > impact_order.index(highest):
                highest = impact
        
        return highest
    
    def _create_combined_summary(self, vision_results: List[Dict]) -> str:
        """Create a combined summary from multiple image analyses"""
        summaries = [r.get('actionable_summary', '') for r in vision_results if r.get('actionable_summary')]
        
        if not summaries:
            return "Multiple screenshots require analysis"
        
        if len(summaries) == 1:
            return summaries[0]
        
        return f"Multiple issues detected: {'; '.join(summaries[:2])}"
    
    def _categorize_with_vision(self, post: Dict, vision_analysis: Dict) -> str:
        """
        Categorize post based on both text and vision analysis
        """
        # Vision-enhanced categories
        if not vision_analysis:
            return self._analyze_text_only(post)
        
        content_type = vision_analysis.get('content_type', '')
        severity = vision_analysis.get('problem_severity', 'none')
        business_impact = vision_analysis.get('business_impact', 'none')
        
        # Critical issues - highest priority
        if severity in ['critical', 'high'] or business_impact in ['productivity_loss', 'data_access_blocked']:
            return 'critical_issue'
        
        # Problem reports with screenshots
        if content_type == 'error_dialog' or vision_analysis.get('error_messages'):
            return 'problem_report'
        
        # Configuration and setup help
        if content_type in ['configuration_screen', 'workflow_setup']:
            return 'configuration_help'
        
        # Success stories and solutions
        if content_type == 'success_message' or 'solution' in post.get('title', '').lower():
            return 'solution_sharing'
        
        # Use cases and implementations
        if content_type in ['dashboard_view', 'workflow_setup'] and severity == 'none':
            return 'use_case'
        
        # Default categorization
        return 'general_discussion'
    
    async def _analyze_text_only(self, post: Dict) -> str:
        """
        Fallback text-only analysis when no images are present
        """
        title = post.get('title', '').lower()
        content = post.get('content', '').lower()
        
        # Simple keyword-based categorization
        if any(word in title + content for word in ['error', 'fail', 'broken', 'issue', 'problem', 'bug']):
            return 'problem_report'
        
        if any(word in title + content for word in ['how to', 'setup', 'configure', 'install']):
            return 'configuration_help'
        
        if any(word in title + content for word in ['solution', 'solved', 'fixed', 'workaround']):
            return 'solution_sharing'
        
        if any(word in title + content for word in ['feature', 'request', 'enhancement', 'improve']):
            return 'feature_request'
        
        return 'general_discussion'
    
    def _generate_mock_vision_analysis(self, image_url: str) -> Dict[str, Any]:
        """
        Generate mock vision analysis when OpenAI API is not available
        """
        # Infer content type from URL patterns
        url_lower = image_url.lower()
        
        if 'error' in url_lower or 'dialog' in url_lower:
            content_type = "error_dialog"
            severity = "high"
            issues = ["Error dialog visible in screenshot"]
            impact = "workflow_broken"
        elif 'config' in url_lower or 'setup' in url_lower:
            content_type = "configuration_screen"
            severity = "medium"
            issues = ["Configuration screen shown"]
            impact = "feature_unavailable"
        elif 'dashboard' in url_lower or 'view' in url_lower:
            content_type = "dashboard_view"
            severity = "low"
            issues = []
            impact = "none"
        else:
            content_type = "other"
            severity = "unknown"
            issues = ["Screenshot content requires analysis"]
            impact = "unknown"
        
        return {
            "content_type": content_type,
            "extracted_issues": issues,
            "error_messages": [],
            "atlassian_products": ["jira"],  # Default assumption
            "configuration_details": [],
            "problem_severity": severity,
            "resolution_hints": [],
            "business_impact": impact,
            "actionable_summary": f"Screenshot shows {content_type.replace('_', ' ')} requiring attention",
            "mock_analysis": True
        }
    
    async def is_image_accessible(self, image_url: str) -> bool:
        """
        Check if image URL is accessible for analysis
        """
        try:
            async with self.session.head(image_url) as response:
                return response.status == 200
        except:
            return False

# Convenience functions
async def analyze_post_images(post: Dict) -> Dict[str, Any]:
    """Analyze images in a single post"""
    async with VisionAnalyzer() as analyzer:
        return await analyzer.analyze_post_with_vision(post)

async def batch_analyze_post_images(posts: List[Dict]) -> List[Dict]:
    """Analyze images across multiple posts"""
    async with VisionAnalyzer() as analyzer:
        results = []
        for post in posts:
            analysis = await analyzer.analyze_post_with_vision(post)
            results.append({
                'post_id': post.get('id'),
                'post_url': post.get('url'),
                **analysis
            })
        return results