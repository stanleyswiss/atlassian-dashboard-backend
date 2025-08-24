"""
Enhanced AI Analysis Service for comprehensive business intelligence
Replaces basic sentiment analysis with actionable categorization and insights
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import openai
import os
from database.operations import DatabaseOperations
from services.vision_analyzer import VisionAnalyzer
from config import settings

logger = logging.getLogger(__name__)

class EnhancedAnalyzer:
    """
    Advanced AI analyzer that combines text and vision analysis for business intelligence
    """
    
    def __init__(self, api_key: str = None):
        # Try multiple sources for API key
        self.api_key = (
            api_key or 
            settings.openai_api_key or 
            os.environ.get("OPENAI_API_KEY") or 
            os.getenv("OPENAI_API_KEY")
        )
        
        logger.info(f"🔑 EnhancedAnalyzer init - API key sources:")
        logger.info(f"  - From parameter: {bool(api_key)}")
        logger.info(f"  - From settings: {bool(settings.openai_api_key)}")
        logger.info(f"  - From os.environ: {bool(os.environ.get('OPENAI_API_KEY'))}")
        logger.info(f"  - From os.getenv: {bool(os.getenv('OPENAI_API_KEY'))}")
        logger.info(f"  - Final API key available: {bool(self.api_key)}, Length: {len(self.api_key) if self.api_key else 0}")
        
        if self.api_key:
            # Try both old and new OpenAI API initialization methods
            try:
                # New OpenAI client (v1.0+)
                self.openai_client = openai.OpenAI(api_key=self.api_key)
                logger.info(f"✅ OpenAI v1.0+ client initialized, prefix: {self.api_key[:7]}...")
            except Exception as e:
                # Fallback to old method
                openai.api_key = self.api_key
                self.openai_client = None
                logger.info(f"✅ OpenAI legacy client initialized, prefix: {self.api_key[:7]}...")
        else:
            logger.warning("❌ No OpenAI API key found - will use mock analysis")
            self.openai_client = None
            
        self.db_ops = DatabaseOperations()
        self.vision_analyzer = VisionAnalyzer(api_key)
    
    async def analyze_post_comprehensive(self, post: Dict) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of a post including vision AI
        """
        try:
            # Get vision analysis if post has images
            async with self.vision_analyzer:
                vision_data = await self.vision_analyzer.analyze_post_with_vision(post)
            
            # Enhanced text analysis
            text_analysis = await self._analyze_text_enhanced(post)
            
            # Combine analyses for final categorization
            enhanced_category = self._determine_enhanced_category(post, text_analysis, vision_data)
            
            # Extract business intelligence
            business_insights = self._extract_business_insights(post, text_analysis, vision_data)
            
            return {
                "post_id": post.get('id'),
                "enhanced_category": enhanced_category,
                "text_analysis": text_analysis,
                "vision_analysis": vision_data,
                "business_insights": business_insights,
                "analysis_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Enhanced analysis failed for post {post.get('id')}: {e}")
            return {
                "post_id": post.get('id'),
                "enhanced_category": "uncategorized",
                "error": str(e)
            }
    
    async def _analyze_text_enhanced(self, post: Dict) -> Dict[str, Any]:
        """
        Enhanced text analysis using OpenAI for better categorization
        """
        try:
            title = post.get('title', '')
            content = post.get('content', '')
            
            prompt = f"""
            Analyze this Atlassian Community forum post and categorize it:

            Title: {title}
            Content: {content[:1000]}

            Return JSON with:
            1. "primary_intent": What is the user trying to achieve? (report_problem, seek_help, share_solution, request_feature, show_use_case, ask_question, share_news)
            2. "urgency_level": How urgent is this? (critical, high, medium, low, none)
            3. "technical_complexity": How complex is the topic? (beginner, intermediate, advanced, expert)
            4. "problem_indicators": Keywords/phrases that suggest problems
            5. "solution_indicators": Keywords/phrases that suggest solutions
            6. "mentioned_products": Which Atlassian products are mentioned
            7. "topic_keywords": Main technical topics/keywords (max 5)
            8. "user_sentiment": How does the user feel? (frustrated, confused, satisfied, excited, neutral)
            9. "resolution_status": Does this seem resolved? (resolved, in_progress, needs_help, unanswered)

            Focus on technical details and business value.
            """
            
            if not self.api_key:
                logger.warning(f"🚫 No API key available for post {post.get('id', 'unknown')} - generating mock analysis")
                return self._generate_mock_text_analysis(post)
            
            logger.info(f"🤖 Making real OpenAI API call for post {post.get('id', 'unknown')}")
            
            messages = [
                {"role": "system", "content": "You are an expert at analyzing technical forum posts and identifying user needs, problems, and solutions."},
                {"role": "user", "content": prompt}
            ]
            
            try:
                if self.openai_client:
                    # New OpenAI client (v1.0+) - synchronous call
                    logger.info("Using OpenAI v1.0+ client (synchronous)")
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",  # Uses latest version automatically
                        messages=messages,
                        max_tokens=500,
                        temperature=0.2
                    )
                    content = response.choices[0].message.content
                    tokens = response.usage.total_tokens
                else:
                    # Legacy OpenAI API
                    logger.info("Using OpenAI legacy API")
                    response = await openai.ChatCompletion.acreate(
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=500,
                        temperature=0.2
                    )
                    content = response.choices[0].message.content
                    tokens = response.usage.total_tokens if hasattr(response, 'usage') else 'unknown'
                
                logger.info(f"✅ OpenAI API call successful for post {post.get('id', 'unknown')}, response tokens: {tokens}")
                logger.info(f"🔍 OpenAI response content: {content[:200]}...")
                
                # Parse response with better JSON handling
                import json
                try:
                    # Try to extract JSON from response if it's embedded in text
                    if '{' in content and '}' in content:
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        json_text = content[json_start:json_end]
                        result = json.loads(json_text)
                        logger.info(f"📊 Parsed AI analysis result: {list(result.keys()) if isinstance(result, dict) else 'invalid'}")
                        return result
                    else:
                        # No JSON found, create structured response from text
                        logger.warning(f"No JSON found in response, creating structured fallback")
                        return self._parse_text_response_to_dict(content, post)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed: {e}, creating structured fallback")
                    return self._parse_text_response_to_dict(content, post)
                
            except Exception as api_error:
                logger.error(f"OpenAI API call failed: {api_error}")
                raise api_error
            
        except Exception as e:
            logger.error(f"Text analysis failed: {e}")
            return self._generate_mock_text_analysis(post)
    
    def _determine_enhanced_category(self, post: Dict, text_analysis: Dict, vision_data: Dict) -> str:
        """
        Determine enhanced category based on combined analysis
        """
        # Priority 1: Critical issues (from vision or text)
        if (vision_data.get('vision_analysis', {}).get('problem_severity') in ['critical', 'high'] or
            text_analysis.get('urgency_level') == 'critical'):
            return 'critical_issue'
        
        # Priority 2: Problem reports with evidence
        if (vision_data.get('has_images') and 
            vision_data.get('vision_analysis', {}).get('content_type') == 'error_dialog'):
            return 'problem_with_evidence'
        
        # Priority 3: Solutions and fixes
        if (text_analysis.get('primary_intent') == 'share_solution' or
            text_analysis.get('resolution_status') == 'resolved'):
            return 'solution_sharing'
        
        # Priority 4: Awesome use cases
        if (text_analysis.get('primary_intent') == 'show_use_case' or
            text_analysis.get('user_sentiment') == 'excited'):
            return 'awesome_use_case'
        
        # Priority 5: Feature requests
        if text_analysis.get('primary_intent') == 'request_feature':
            return 'feature_request'
        
        # Priority 6: Configuration help
        if (text_analysis.get('primary_intent') == 'seek_help' and
            text_analysis.get('technical_complexity') in ['beginner', 'intermediate']):
            return 'configuration_help'
        
        # Priority 7: Advanced technical discussions
        if text_analysis.get('technical_complexity') in ['advanced', 'expert']:
            return 'advanced_technical'
        
        # Default
        return 'general_discussion'
    
    def _extract_business_insights(self, post: Dict, text_analysis: Dict, vision_data: Dict) -> Dict[str, Any]:
        """
        Extract actionable business insights from the analysis
        """
        insights = {
            "business_value": "low",
            "atlassian_team_attention": False,
            "product_improvement_opportunity": False,
            "user_experience_impact": "minimal",
            "documentation_gap": False,
            "training_opportunity": False
        }
        
        # High business value indicators
        high_value_indicators = [
            text_analysis.get('urgency_level') in ['critical', 'high'],
            vision_data.get('vision_analysis', {}).get('business_impact') in ['productivity_loss', 'data_access_blocked'],
            text_analysis.get('primary_intent') == 'report_problem',
            len(text_analysis.get('mentioned_products', [])) > 1  # Cross-product issues
        ]
        
        if any(high_value_indicators):
            insights["business_value"] = "high"
            insights["atlassian_team_attention"] = True
        
        # Product improvement opportunities
        if (text_analysis.get('primary_intent') == 'request_feature' or
            text_analysis.get('user_sentiment') == 'frustrated'):
            insights["product_improvement_opportunity"] = True
        
        # User experience impact
        if vision_data.get('vision_analysis', {}).get('business_impact') in ['workflow_broken', 'productivity_loss']:
            insights["user_experience_impact"] = "high"
        elif text_analysis.get('user_sentiment') == 'frustrated':
            insights["user_experience_impact"] = "medium"
        
        # Documentation gaps
        if (text_analysis.get('primary_intent') == 'seek_help' and
            text_analysis.get('technical_complexity') == 'beginner'):
            insights["documentation_gap"] = True
        
        # Training opportunities
        if (text_analysis.get('technical_complexity') in ['advanced', 'expert'] and
            text_analysis.get('primary_intent') == 'share_solution'):
            insights["training_opportunity"] = True
        
        return insights
    
    def _parse_text_response_to_dict(self, content: str, post: Dict) -> Dict[str, Any]:
        """
        Parse non-JSON OpenAI response into structured data
        """
        logger.info(f"📝 Parsing text response to structured data")
        
        # Create default structure
        result = {
            "primary_intent": "ask_question",
            "urgency_level": "medium",
            "technical_complexity": "intermediate", 
            "problem_indicators": [],
            "solution_indicators": [],
            "mentioned_products": [],
            "topic_keywords": [],
            "user_sentiment": "neutral",
            "resolution_status": "unanswered"
        }
        
        # Basic keyword analysis on the response content and original post
        content_lower = content.lower()
        title_content = f"{post.get('title', '')} {post.get('content', '')}".lower()
        
        # Determine intent from keywords
        if any(word in content_lower for word in ['error', 'issue', 'problem', 'broken', 'fail']):
            result["primary_intent"] = "report_problem"
        elif any(word in content_lower for word in ['solution', 'fix', 'resolve', 'workaround']):
            result["primary_intent"] = "share_solution"
        elif any(word in content_lower for word in ['how to', 'help', 'guidance']):
            result["primary_intent"] = "seek_help"
        
        # Determine urgency
        if any(word in content_lower for word in ['critical', 'urgent', 'blocking']):
            result["urgency_level"] = "critical"
        elif any(word in content_lower for word in ['important', 'asap']):
            result["urgency_level"] = "high"
        
        # Determine sentiment
        if any(word in content_lower for word in ['frustrated', 'annoying', 'terrible']):
            result["user_sentiment"] = "frustrated"
        elif any(word in content_lower for word in ['great', 'excellent', 'perfect']):
            result["user_sentiment"] = "excited"
        
        # Extract products mentioned
        products = ['jira', 'confluence', 'bitbucket', 'jsm', 'rovo']
        mentioned = [p for p in products if p in title_content]
        result["mentioned_products"] = mentioned
        
        # Basic keywords from title
        title = post.get('title', '')
        keywords = [word.strip() for word in title.split() if len(word) > 3][:5]
        result["topic_keywords"] = keywords
        
        logger.info(f"📊 Created structured analysis from text response")
        return result
    
    async def generate_business_intelligence_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate comprehensive business intelligence report
        """
        try:
            # Get recent posts with enhanced analysis
            posts = await self._get_analyzed_posts(days)
            
            if not posts:
                return {"error": "No analyzed posts available"}
            
            # Generate different insight categories
            critical_issues = self._extract_critical_issues(posts)
            awesome_discoveries = self._extract_awesome_discoveries(posts)
            trending_solutions = self._extract_trending_solutions(posts)
            unresolved_problems = self._extract_unresolved_problems(posts)
            feature_requests = self._extract_feature_requests(posts)
            
            # Executive summary
            executive_summary = await self._generate_executive_summary(
                critical_issues, awesome_discoveries, trending_solutions, 
                unresolved_problems, feature_requests
            )
            
            return {
                "generated_at": datetime.now().isoformat(),
                "time_period": f"Last {days} days",
                "total_posts_analyzed": len(posts),
                "executive_summary": executive_summary,
                "critical_issues": critical_issues,
                "awesome_discoveries": awesome_discoveries,
                "trending_solutions": trending_solutions,
                "unresolved_problems": unresolved_problems,
                "feature_requests": feature_requests,
                "business_metrics": self._calculate_business_metrics(posts)
            }
            
        except Exception as e:
            logger.error(f"Business intelligence report generation failed: {e}")
            return {"error": str(e)}
    
    def _extract_critical_issues(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract critical issues that need immediate attention"""
        critical_posts = [
            p for p in posts 
            if p.get('enhanced_category') in ['critical_issue', 'problem_with_evidence']
        ]
        
        # Group by problem type and count occurrences
        problem_groups = defaultdict(list)
        for post in critical_posts:
            vision_analysis = post.get('vision_analysis', {})
            issues = vision_analysis.get('extracted_issues', [])
            
            # Group similar issues
            for issue in issues:
                key = self._normalize_issue_key(issue)
                problem_groups[key].append(post)
        
        # Format for dashboard
        critical_issues = []
        for problem_key, related_posts in problem_groups.items():
            if len(related_posts) >= 2:  # Multiple reports of same issue
                critical_issues.append({
                    "issue_title": problem_key.replace('_', ' ').title(),
                    "severity": "high",
                    "report_count": len(related_posts),
                    "affected_products": list(set([
                        product for post in related_posts 
                        for product in post.get('text_analysis', {}).get('mentioned_products', [])
                    ])),
                    "first_reported": min(post.get('created_at', '') for post in related_posts),
                    "latest_report": max(post.get('created_at', '') for post in related_posts),
                    "sample_posts": [
                        {
                            "title": post.get('title'),
                            "url": post.get('url'),
                            "author": post.get('author')
                        } for post in related_posts[:3]
                    ],
                    "business_impact": self._assess_business_impact(related_posts)
                })
        
        # Sort by severity and report count
        critical_issues.sort(key=lambda x: (x['severity'] == 'critical', x['report_count']), reverse=True)
        return critical_issues[:10]  # Top 10 critical issues
    
    def _extract_awesome_discoveries(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract impressive use cases and success stories"""
        awesome_posts = [
            p for p in posts 
            if p.get('enhanced_category') in ['awesome_use_case', 'solution_sharing']
        ]
        
        discoveries = []
        for post in awesome_posts:
            text_analysis = post.get('text_analysis', {})
            
            if text_analysis.get('user_sentiment') in ['excited', 'satisfied']:
                discoveries.append({
                    "title": post.get('title'),
                    "summary": text_analysis.get('actionable_summary', 'Interesting use case shared'),
                    "author": post.get('author'),
                    "url": post.get('url'),
                    "products_used": text_analysis.get('mentioned_products', []),
                    "technical_level": text_analysis.get('technical_complexity', 'intermediate'),
                    "has_screenshots": post.get('vision_analysis', {}).get('has_images', False),
                    "engagement_potential": "high" if len(text_analysis.get('topic_keywords', [])) > 3 else "medium"
                })
        
        # Sort by engagement potential and technical level
        discoveries.sort(key=lambda x: (x['engagement_potential'] == 'high', x['technical_level'] == 'expert'), reverse=True)
        return discoveries[:5]  # Top 5 discoveries
    
    def _extract_trending_solutions(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract solutions and workarounds that are working for users"""
        solution_posts = [
            p for p in posts 
            if p.get('enhanced_category') == 'solution_sharing' or
               p.get('text_analysis', {}).get('resolution_status') == 'resolved'
        ]
        
        solutions = []
        for post in solution_posts:
            text_analysis = post.get('text_analysis', {})
            vision_analysis = post.get('vision_analysis', {})
            
            solutions.append({
                "solution_title": post.get('title'),
                "problem_solved": self._extract_problem_from_solution(post),
                "solution_type": self._categorize_solution_type(text_analysis, vision_analysis),
                "author": post.get('author'),
                "url": post.get('url'),
                "products_affected": text_analysis.get('mentioned_products', []),
                "technical_level": text_analysis.get('technical_complexity', 'intermediate'),
                "has_visual_guide": vision_analysis.get('has_images', False),
                "effectiveness_score": self._calculate_solution_effectiveness(post, text_analysis)
            })
        
        # Sort by effectiveness and recency
        solutions.sort(key=lambda x: (x['effectiveness_score'], x.get('created_at', '')), reverse=True)
        return solutions[:8]  # Top 8 solutions
    
    def _extract_unresolved_problems(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract problems that still need attention"""
        problem_posts = [
            p for p in posts 
            if p.get('enhanced_category') in ['critical_issue', 'problem_with_evidence', 'problem_report'] and
               p.get('text_analysis', {}).get('resolution_status') in ['needs_help', 'unanswered']
        ]
        
        unresolved = []
        for post in problem_posts:
            text_analysis = post.get('text_analysis', {})
            vision_analysis = post.get('vision_analysis', {})
            
            unresolved.append({
                "problem_title": post.get('title'),
                "urgency": text_analysis.get('urgency_level', 'medium'),
                "days_unresolved": self._calculate_days_since_post(post),
                "author": post.get('author'),
                "url": post.get('url'),
                "affected_products": text_analysis.get('mentioned_products', []),
                "problem_type": self._categorize_problem_type(text_analysis, vision_analysis),
                "has_screenshots": vision_analysis.get('has_images', False),
                "business_impact": vision_analysis.get('vision_analysis', {}).get('business_impact', 'unknown'),
                "help_potential": self._assess_help_potential(post, text_analysis)
            })
        
        # Sort by urgency and days unresolved
        unresolved.sort(key=lambda x: (
            x['urgency'] == 'critical',
            x['urgency'] == 'high', 
            x['days_unresolved']
        ), reverse=True)
        
        return unresolved[:10]  # Top 10 unresolved
    
    def _extract_feature_requests(self, posts: List[Dict]) -> List[Dict[str, Any]]:
        """Extract feature requests and enhancement suggestions"""
        feature_posts = [
            p for p in posts 
            if p.get('enhanced_category') == 'feature_request' or
               p.get('text_analysis', {}).get('primary_intent') == 'request_feature'
        ]
        
        requests = []
        for post in feature_posts:
            text_analysis = post.get('text_analysis', {})
            
            requests.append({
                "feature_title": post.get('title'),
                "requested_for": text_analysis.get('mentioned_products', []),
                "user_value": self._assess_user_value(post, text_analysis),
                "implementation_complexity": text_analysis.get('technical_complexity', 'medium'),
                "author": post.get('author'),
                "url": post.get('url'),
                "similar_requests": 1,  # TODO: Group similar requests
                "business_justification": self._extract_business_justification(post)
            })
        
        return requests[:6]  # Top 6 feature requests
    
    async def _generate_executive_summary(self, critical_issues, awesome_discoveries, 
                                        trending_solutions, unresolved_problems, feature_requests) -> Dict[str, Any]:
        """
        Generate executive summary for business stakeholders
        """
        try:
            summary_data = {
                "critical_count": len(critical_issues),
                "solution_count": len(trending_solutions), 
                "unresolved_count": len(unresolved_problems),
                "feature_request_count": len(feature_requests),
                "discovery_count": len(awesome_discoveries)
            }
            
            # Key highlights
            highlights = []
            
            if critical_issues:
                top_critical = critical_issues[0]
                highlights.append(f"🚨 Critical: {top_critical['issue_title']} ({top_critical['report_count']} reports)")
            
            if awesome_discoveries:
                top_discovery = awesome_discoveries[0]
                highlights.append(f"💡 Highlight: {top_discovery['title']}")
            
            if trending_solutions:
                solution_count = len(trending_solutions)
                highlights.append(f"✅ {solution_count} trending solutions shared this week")
            
            # Business impact assessment
            total_impact_posts = len([
                p for p in unresolved_problems 
                if p.get('business_impact') in ['productivity_loss', 'workflow_broken']
            ])
            
            return {
                "week_summary": f"Analyzed {sum(summary_data.values())} high-value community interactions",
                "key_highlights": highlights,
                "business_impact": {
                    "high_impact_unresolved": total_impact_posts,
                    "solution_sharing_trend": "increasing" if len(trending_solutions) > 3 else "stable",
                    "critical_attention_needed": len(critical_issues) > 0
                },
                "recommendations": self._generate_recommendations(
                    critical_issues, unresolved_problems, feature_requests
                )
            }
            
        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return {
                "week_summary": "Business intelligence analysis completed",
                "error": str(e)
            }
    
    def _generate_recommendations(self, critical_issues, unresolved_problems, feature_requests) -> List[str]:
        """Generate actionable recommendations for Atlassian teams"""
        recommendations = []
        
        if critical_issues:
            recommendations.append("Immediate action needed on critical issues - assign engineering resources")
        
        if len(unresolved_problems) > 5:
            recommendations.append("High volume of unresolved problems - consider documentation review")
        
        if len(feature_requests) > 3:
            top_products = Counter([
                product for req in feature_requests 
                for product in req.get('requested_for', [])
            ])
            if top_products:
                top_product = top_products.most_common(1)[0][0]
                recommendations.append(f"Feature request trend detected for {top_product} - product team review recommended")
        
        return recommendations
    
    # Helper methods
    def _normalize_issue_key(self, issue_text: str) -> str:
        """Normalize issue text for grouping similar problems"""
        return re.sub(r'[^a-zA-Z0-9\s]', '', issue_text.lower()).replace(' ', '_')
    
    def _assess_business_impact(self, posts: List[Dict]) -> str:
        """Assess business impact of a group of posts"""
        impact_counts = Counter([
            post.get('vision_analysis', {}).get('business_impact', 'unknown')
            for post in posts
        ])
        
        if impact_counts.get('productivity_loss', 0) > 0:
            return "high"
        elif impact_counts.get('workflow_broken', 0) > 0:
            return "medium"
        else:
            return "low"
    
    def _calculate_days_since_post(self, post: Dict) -> int:
        """Calculate days since post was created"""
        try:
            created_at = post.get('created_at')
            if isinstance(created_at, str):
                post_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            else:
                post_date = created_at
            
            return (datetime.now() - post_date.replace(tzinfo=None)).days
        except:
            return 0
    
    def _categorize_problem_type(self, text_analysis: Dict, vision_analysis: Dict) -> str:
        """Categorize the type of problem based on analysis"""
        if vision_analysis.get('vision_analysis', {}).get('content_type') == 'error_dialog':
            return "system_error"
        
        keywords = text_analysis.get('topic_keywords', [])
        if any('config' in k.lower() for k in keywords):
            return "configuration_issue"
        elif any('api' in k.lower() for k in keywords):
            return "api_integration"
        elif any('performance' in k.lower() for k in keywords):
            return "performance_issue"
        else:
            return "general_problem"
    
    def _assess_help_potential(self, post: Dict, text_analysis: Dict) -> str:
        """Assess how likely this problem is to get community help"""
        complexity = text_analysis.get('technical_complexity', 'medium')
        has_screenshots = post.get('vision_analysis', {}).get('has_images', False)
        
        if complexity == 'beginner' and has_screenshots:
            return "high"
        elif complexity in ['intermediate', 'advanced']:
            return "medium"
        else:
            return "low"
    
    def _assess_user_value(self, post: Dict, text_analysis: Dict) -> str:
        """Assess the business value of a feature request"""
        mentioned_products = text_analysis.get('mentioned_products', [])
        technical_complexity = text_analysis.get('technical_complexity', 'medium')
        
        if len(mentioned_products) > 1 and technical_complexity == 'expert':
            return "high"
        elif technical_complexity in ['intermediate', 'advanced']:
            return "medium"
        else:
            return "low"
    
    def _extract_business_justification(self, post: Dict) -> str:
        """Extract business justification from feature request"""
        content = post.get('content', '')
        title = post.get('title', '')
        
        # Look for business-related keywords
        business_keywords = ['efficiency', 'productivity', 'workflow', 'automation', 'scalability', 'compliance']
        
        for keyword in business_keywords:
            if keyword in content.lower() or keyword in title.lower():
                return f"Related to {keyword}"
        
        return "General improvement"
    
    def _extract_problem_from_solution(self, post: Dict) -> str:
        """Extract what problem a solution post is addressing"""
        title = post.get('title', '').lower()
        
        if 'fix' in title:
            return title.replace('fix', '').replace('for', '').strip()
        elif 'solution' in title:
            return title.replace('solution', '').replace('for', '').strip()
        else:
            return "General problem"
    
    def _categorize_solution_type(self, text_analysis: Dict, vision_analysis: Dict) -> str:
        """Categorize the type of solution"""
        if vision_analysis.get('has_images'):
            return "visual_guide"
        elif text_analysis.get('technical_complexity') == 'expert':
            return "advanced_solution"
        elif 'config' in ' '.join(text_analysis.get('topic_keywords', [])).lower():
            return "configuration_fix"
        else:
            return "general_solution"
    
    def _calculate_solution_effectiveness(self, post: Dict, text_analysis: Dict) -> int:
        """Calculate a solution effectiveness score"""
        score = 0
        
        # Higher score for detailed solutions
        if text_analysis.get('technical_complexity') in ['advanced', 'expert']:
            score += 3
        
        # Higher score for solutions with screenshots
        if post.get('vision_analysis', {}).get('has_images'):
            score += 2
        
        # Higher score for resolved status
        if text_analysis.get('resolution_status') == 'resolved':
            score += 3
        
        return score
    
    def _calculate_business_metrics(self, posts: List[Dict]) -> Dict[str, Any]:
        """Calculate business metrics from analyzed posts"""
        total_posts = len(posts)
        
        category_counts = Counter([p.get('enhanced_category', 'uncategorized') for p in posts])
        
        # Calculate percentages
        critical_percentage = (category_counts.get('critical_issue', 0) / total_posts * 100) if total_posts > 0 else 0
        solution_percentage = (category_counts.get('solution_sharing', 0) / total_posts * 100) if total_posts > 0 else 0
        
        return {
            "total_posts": total_posts,
            "critical_issue_rate": round(critical_percentage, 1),
            "solution_sharing_rate": round(solution_percentage, 1),
            "category_breakdown": dict(category_counts),
            "community_health_score": self._calculate_health_score(category_counts, total_posts)
        }
    
    def _calculate_health_score(self, category_counts: Counter, total_posts: int) -> int:
        """Calculate overall community health score (0-100)"""
        if total_posts == 0:
            return 50
        
        # Start with base score
        score = 50
        
        # Positive indicators
        score += min(category_counts.get('solution_sharing', 0) * 2, 20)  # Max +20 for solutions
        score += min(category_counts.get('awesome_use_case', 0) * 3, 15)  # Max +15 for use cases
        
        # Negative indicators  
        score -= min(category_counts.get('critical_issue', 0) * 5, 30)  # Max -30 for critical issues
        score -= min(category_counts.get('problem_report', 0) * 2, 20)  # Max -20 for problems
        
        return max(0, min(100, score))
    
    async def _get_analyzed_posts(self, days: int) -> List[Dict]:
        """Get posts with enhanced analysis from database"""
        try:
            from database.connection import get_session
            from database.models import PostDB
            
            cutoff_date = datetime.now() - timedelta(days=days)
            
            with get_session() as db:
                posts = db.query(PostDB).filter(
                    PostDB.created_at >= cutoff_date
                ).order_by(PostDB.created_at.desc()).all()
                
                # Convert to dict format for analysis
                result = []
                for post in posts:
                    result.append({
                        'id': post.id,
                        'title': post.title,
                        'content': post.content,
                        'category': post.category,
                        'author': post.author,
                        'url': post.url,
                        'created_at': post.created_at,
                        'sentiment_score': post.sentiment_score,
                        'sentiment_label': post.sentiment_label,
                        # Enhanced analysis fields (if they exist)
                        'enhanced_category': getattr(post, 'enhanced_category', None),
                        'vision_analysis': getattr(post, 'vision_analysis', {}),
                        'text_analysis': getattr(post, 'text_analysis', {})
                    })
                
                return result
                
        except Exception as e:
            logger.error(f"Error getting analyzed posts: {e}")
            return []
    
    def _generate_mock_text_analysis(self, post: Dict) -> Dict[str, Any]:
        """Generate mock text analysis when OpenAI is not available"""
        logger.warning(f"🎭 Generating MOCK analysis for post {post.get('id', 'unknown')} - this is fake sentiment data!")
        title = post.get('title', '').lower()
        content = post.get('content', '').lower()
        
        # Simple keyword-based analysis
        if any(word in title + content for word in ['error', 'fail', 'broken', 'crash']):
            primary_intent = "report_problem"
            urgency = "high"
            user_sentiment = "frustrated"
        elif any(word in title + content for word in ['how to', 'help', 'question']):
            primary_intent = "seek_help"
            urgency = "medium"  
            user_sentiment = "confused"
        elif any(word in title + content for word in ['solution', 'fixed', 'solved', 'workaround']):
            primary_intent = "share_solution"
            urgency = "low"
            user_sentiment = "satisfied"
        elif any(word in title + content for word in ['feature', 'request', 'enhancement']):
            primary_intent = "request_feature"
            urgency = "medium"
            user_sentiment = "neutral"
        else:
            primary_intent = "ask_question"
            urgency = "low"
            user_sentiment = "neutral"
        
        return {
            "primary_intent": primary_intent,
            "urgency_level": urgency,
            "technical_complexity": "intermediate",
            "problem_indicators": ["mock analysis"],
            "solution_indicators": [],
            "mentioned_products": ["jira"],  # Default assumption
            "topic_keywords": ["general", "question"],
            "user_sentiment": user_sentiment,
            "resolution_status": "unanswered",
            "mock_analysis": True
        }

# Convenience functions
async def analyze_post_enhanced(post: Dict) -> Dict[str, Any]:
    """Analyze a single post with enhanced AI"""
    analyzer = EnhancedAnalyzer()
    return await analyzer.analyze_post_comprehensive(post)

async def generate_business_intelligence(days: int = 7) -> Dict[str, Any]:
    """Generate business intelligence report"""
    analyzer = EnhancedAnalyzer()
    return await analyzer.generate_business_intelligence_report(days)