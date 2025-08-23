import asyncio
from typing import List, Dict, Optional, Tuple
from openai import AsyncOpenAI
import json
import re
from datetime import datetime
import logging
from config import settings
from models import SentimentLabel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIAnalyzer:
    """
    AI-powered analyzer for sentiment analysis and topic extraction
    Uses OpenAI GPT-4o-mini for efficient processing
    """
    
    def __init__(self, api_key: Optional[str] = None):
        # Try to get API key from settings system first
        if not api_key:
            try:
                from api.settings import get_openai_api_key
                api_key = get_openai_api_key()
            except ImportError:
                # Fallback to config if settings system not available
                api_key = settings.openai_api_key
        
        if not api_key:
            raise ValueError("OpenAI API key is required. Please configure it in Settings.")
            
        self.client = AsyncOpenAI(api_key=api_key)
    
    async def analyze_sentiment(self, text: str) -> Dict[str, any]:
        """Simple sentiment analysis method for testing"""
        return await self.analyze_sentiment_single(text)
        
    async def analyze_sentiment_single(self, text: str) -> Dict[str, any]:
        """Analyze sentiment for a single text"""
        try:
            prompt = f"""
Analyze the sentiment of this community forum post. Return a JSON response with:
1. sentiment_score: float between -1.0 (very negative) and 1.0 (very positive)
2. sentiment_label: "positive", "negative", or "neutral"
3. confidence: float between 0.0 and 1.0
4. key_emotions: list of detected emotions (e.g., "frustrated", "excited", "confused")
5. topics: list of main topics/keywords (max 5)

Post text:
{text[:2000]}  

Response format:
{{
    "sentiment_score": -0.3,
    "sentiment_label": "negative",
    "confidence": 0.85,
    "key_emotions": ["frustrated", "confused"],
    "topics": ["bug", "performance", "jira workflow"]
}}
"""

            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing sentiment and topics in technical forum posts. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                result = json.loads(result_text)
                
                # Validate and clean up the result
                result['sentiment_score'] = max(-1.0, min(1.0, float(result.get('sentiment_score', 0.0))))
                result['confidence'] = max(0.0, min(1.0, float(result.get('confidence', 0.0))))
                
                # Ensure sentiment_label is valid
                valid_labels = ['positive', 'negative', 'neutral']
                if result.get('sentiment_label') not in valid_labels:
                    # Infer from score
                    score = result['sentiment_score']
                    if score > 0.1:
                        result['sentiment_label'] = 'positive'
                    elif score < -0.1:
                        result['sentiment_label'] = 'negative'
                    else:
                        result['sentiment_label'] = 'neutral'
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response was: {result_text}")
                
                # Fallback analysis
                return self._fallback_sentiment_analysis(text)
                
        except Exception as e:
            logger.error(f"Error in AI sentiment analysis: {e}")
            return self._fallback_sentiment_analysis(text)
            
    def _fallback_sentiment_analysis(self, text: str) -> Dict[str, any]:
        """Simple fallback sentiment analysis using keyword matching"""
        text_lower = text.lower()
        
        # Simple keyword-based sentiment
        positive_keywords = ['great', 'excellent', 'awesome', 'perfect', 'love', 'amazing', 'fantastic', 'solved', 'working', 'thanks', 'helpful']
        negative_keywords = ['bug', 'error', 'problem', 'issue', 'broken', 'crash', 'fail', 'wrong', 'terrible', 'awful', 'hate', 'frustrated']
        neutral_keywords = ['question', 'how', 'help', 'can', 'would', 'should', 'need', 'want']
        
        pos_count = sum(1 for word in positive_keywords if word in text_lower)
        neg_count = sum(1 for word in negative_keywords if word in text_lower)
        
        if pos_count > neg_count:
            sentiment_score = min(0.8, pos_count * 0.2)
            sentiment_label = 'positive'
        elif neg_count > pos_count:
            sentiment_score = max(-0.8, -neg_count * 0.2)
            sentiment_label = 'negative'
        else:
            sentiment_score = 0.0
            sentiment_label = 'neutral'
            
        # Extract basic topics
        topics = []
        topic_patterns = [
            r'\bjira\b', r'\bconfluence\b', r'\bbitbucket\b', r'\brovo\b',
            r'\bbug\b', r'\berror\b', r'\bworkflow\b', r'\bplugin\b',
            r'\bapi\b', r'\bintegration\b', r'\bpermission\b', r'\bauth\b'
        ]
        
        for pattern in topic_patterns:
            if re.search(pattern, text_lower):
                topics.append(pattern.strip('\\b'))
        
        return {
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'confidence': 0.6,  # Lower confidence for fallback
            'key_emotions': [],
            'topics': topics[:5]
        }
        
    async def analyze_sentiment_batch(self, texts: List[str]) -> List[Dict[str, any]]:
        """Analyze sentiment for multiple texts efficiently"""
        logger.info(f"🤖 Analyzing sentiment for {len(texts)} posts")
        
        # Process in batches to respect rate limits
        batch_size = settings.sentiment_batch_size
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self.analyze_sentiment_single(text) for text in batch],
                return_exceptions=True
            )
            
            # Handle exceptions in batch results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Error analyzing text {i+j}: {result}")
                    results.append(self._fallback_sentiment_analysis(batch[j]))
                else:
                    results.append(result)
            
            # Rate limiting between batches
            if i + batch_size < len(texts):
                await asyncio.sleep(1.0)
                
        logger.info(f"✅ Completed sentiment analysis for {len(results)} posts")
        return results
        
    async def extract_trending_topics(self, posts: List[Dict]) -> List[Dict[str, any]]:
        """Extract and rank trending topics from posts"""
        try:
            # Prepare text for analysis
            all_content = []
            for post in posts:
                content = f"{post.get('title', '')} {post.get('content', '')}"
                all_content.append(content)
            
            combined_text = " ".join(all_content)[:8000]  # Limit for API
            
            prompt = f"""
Analyze this collection of forum posts and identify the top trending topics and issues.

Return a JSON array of the top 10 trending topics with:
1. topic: the topic name/phrase
2. frequency: estimated frequency (1-100)
3. trend_score: trending score (1-100)
4. category: type (e.g., "bug", "feature", "question", "announcement")
5. sentiment: overall sentiment for this topic ("positive", "negative", "neutral")

Content to analyze:
{combined_text}

Format:
[
    {{
        "topic": "workflow permissions",
        "frequency": 15,
        "trend_score": 85,
        "category": "bug",
        "sentiment": "negative"
    }}
]
"""

            response = await self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert at identifying trending topics in technical forums. Always return valid JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            result_text = response.choices[0].message.content.strip()
            topics = json.loads(result_text)
            
            # Validate and sort by trend_score
            valid_topics = []
            for topic in topics:
                if isinstance(topic, dict) and 'topic' in topic:
                    topic['frequency'] = max(1, min(100, topic.get('frequency', 1)))
                    topic['trend_score'] = max(1, min(100, topic.get('trend_score', 1)))
                    valid_topics.append(topic)
            
            return sorted(valid_topics, key=lambda x: x['trend_score'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error extracting trending topics: {e}")
            return []
            
    async def analyze_posts_complete(self, posts: List[Dict]) -> Dict[str, any]:
        """Complete analysis of posts including sentiment and topics"""
        logger.info(f"🔍 Starting complete analysis of {len(posts)} posts")
        
        # Extract texts for sentiment analysis
        texts = []
        for post in posts:
            text = f"{post.get('title', '')} {post.get('content', '')}"
            texts.append(text)
        
        # Run sentiment analysis and topic extraction in parallel
        sentiment_results, trending_topics = await asyncio.gather(
            self.analyze_sentiment_batch(texts),
            self.extract_trending_topics(posts),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(sentiment_results, Exception):
            logger.error(f"Sentiment analysis failed: {sentiment_results}")
            sentiment_results = [self._fallback_sentiment_analysis(text) for text in texts]
            
        if isinstance(trending_topics, Exception):
            logger.error(f"Topic extraction failed: {trending_topics}")
            trending_topics = []
        
        # Combine results with posts
        analyzed_posts = []
        for i, post in enumerate(posts):
            if i < len(sentiment_results):
                sentiment = sentiment_results[i]
                enhanced_post = {
                    **post,
                    'sentiment_score': sentiment['sentiment_score'],
                    'sentiment_label': sentiment['sentiment_label'],
                    'ai_confidence': sentiment['confidence'],
                    'key_emotions': sentiment.get('key_emotions', []),
                    'extracted_topics': sentiment.get('topics', [])
                }
                analyzed_posts.append(enhanced_post)
                
        # Calculate overall statistics
        sentiment_scores = [r['sentiment_score'] for r in sentiment_results]
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0
        
        sentiment_breakdown = {
            'positive': len([s for s in sentiment_results if s['sentiment_label'] == 'positive']),
            'negative': len([s for s in sentiment_results if s['sentiment_label'] == 'negative']),
            'neutral': len([s for s in sentiment_results if s['sentiment_label'] == 'neutral'])
        }
        
        result = {
            'analyzed_posts': analyzed_posts,
            'trending_topics': trending_topics,
            'sentiment_summary': {
                'average_sentiment': avg_sentiment,
                'sentiment_breakdown': sentiment_breakdown,
                'total_posts': len(posts)
            },
            'analysis_timestamp': datetime.now()
        }
        
        logger.info(f"✅ Complete analysis finished. Avg sentiment: {avg_sentiment:.2f}")
        return result

# Helper function for easy usage
async def analyze_community_posts(posts: List[Dict], api_key: Optional[str] = None) -> Dict[str, any]:
    """Convenience function to analyze a list of posts"""
    analyzer = AIAnalyzer(api_key)
    return await analyzer.analyze_posts_complete(posts)