import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict
from database.operations import DatabaseOperations

class DemoDataGenerator:
    """
    Generate realistic demo data for the Atlassian Community Dashboard
    This simulates live scraping while we debug the actual scraper
    """
    
    def __init__(self):
        self.db_ops = DatabaseOperations()
        # Skip AI analyzer for demo - we'll generate mock sentiment data
        
    # Sample realistic post data
    SAMPLE_POSTS = [
        {
            "titles": [
                "Jira automation rules not working after upgrade",
                "How to configure workflow permissions in Jira",
                "Issue with JQL query performance", 
                "Custom field not showing in issue screen",
                "Bulk edit issues - missing options",
                "Setting up agile boards for multiple teams",
                "Jira API rate limiting questions",
                "Integration with Slack notifications"
            ],
            "category": "jira",
            "authors": ["JiraAdmin", "ProjectLead", "DevOpsTeam", "ScrumMaster", "TechUser"]
        },
        {
            "titles": [
                "JSM portal customization best practices",
                "SLA policies not triggering correctly",
                "Customer approval workflows in JSM", 
                "ITSM integration with external tools",
                "Automated request routing setup",
                "JSM reporting dashboard issues",
                "Knowledge base article management",
                "Service desk queue configuration"
            ],
            "category": "jsm",
            "authors": ["ServiceDesk", "ITManager", "SupportTeam", "JSMAdmin", "HelpDesk"]
        },
        {
            "titles": [
                "Confluence page templates not loading",
                "Space permissions and user access",
                "Macro compatibility after update",
                "Database connection issues",
                "Content indexing and search problems",
                "Page restrictions and visibility", 
                "Mobile app synchronization",
                "Third-party app integration"
            ],
            "category": "confluence", 
            "authors": ["ContentManager", "WikiAdmin", "DocWriter", "TeamLead", "KnowledgeBase"]
        },
        {
            "titles": [
                "Rovo search not returning results",
                "AI assistant setup questions",
                "Data connector configuration",
                "Rovo agents customization help",
                "Integration with existing tools",
                "Rovo Chat functionality issues",
                "Permission settings for AI features",
                "Rovo analytics and insights"
            ],
            "category": "rovo",
            "authors": ["AITeam", "DataAnalyst", "RovoAdmin", "InnovationLead", "TechExplorer"]
        },
        {
            "titles": [
                "Scheduled maintenance this weekend",
                "New feature rollout announcement", 
                "Security update - action required",
                "Product roadmap updates Q1 2025",
                "Community guidelines update",
                "Upcoming training webinars",
                "Service status and improvements",
                "Partnership announcement"
            ],
            "category": "announcements",
            "authors": ["AtlassianTeam", "ProductManager", "CommunityManager", "SecurityTeam", "DevRel"]
        }
    ]
    
    CONTENT_TEMPLATES = [
        "I'm experiencing an issue with {topic}. Has anyone else encountered this?",
        "Looking for best practices on {topic}. Any recommendations?", 
        "We recently upgraded and now {topic} is not working as expected.",
        "Can someone help with configuring {topic}? Documentation unclear.",
        "Great news! We've resolved the {topic} issue. Here's how:",
        "Warning: Be careful with {topic} settings - this can cause problems.",
        "Step-by-step guide for {topic} that worked for our team.",
        "Feature request: Would love to see improvements to {topic}."
    ]
    
    TOPICS = [
        "workflow automation", "user permissions", "API integration", 
        "database performance", "search functionality", "mobile access",
        "third-party apps", "security settings", "reporting features",
        "data migration", "backup procedures", "system monitoring"
    ]
    
    async def generate_realistic_posts(self, num_posts: int = 30) -> List[Dict]:
        """Generate realistic demo posts"""
        posts = []
        
        for i in range(num_posts):
            # Pick random category
            category_data = random.choice(self.SAMPLE_POSTS)
            
            # Generate post data
            title = random.choice(category_data["titles"])
            author = random.choice(category_data["authors"])
            category = category_data["category"]
            topic = random.choice(self.TOPICS)
            content_template = random.choice(self.CONTENT_TEMPLATES)
            content = content_template.format(topic=topic)
            
            # Add more realistic content
            if random.random() > 0.6:  # 40% chance of longer content
                content += f"\n\nAdditional details: We're running version 9.x.x and this started after the recent update. The issue affects about {random.randint(10, 500)} users in our organization."
            
            if random.random() > 0.7:  # 30% chance of solution
                content += "\n\nUPDATE: Found the solution! Thanks everyone for the help."
            
            # Generate realistic timestamp (within last 7 days)
            days_ago = random.randint(0, 7)
            hours_ago = random.randint(0, 23)
            post_date = datetime.now() - timedelta(days=days_ago, hours=hours_ago)
            
            # Generate realistic Atlassian community URLs
            realistic_urls = {
                'jira': f"https://community.atlassian.com/t5/Jira-questions/jira-question-{i+1000}/qaq-p/{i+100000}",
                'jsm': f"https://community.atlassian.com/t5/Jira-Service-Management/jsm-topic-{i+1000}/qaq-p/{i+200000}",
                'confluence': f"https://community.atlassian.com/t5/Confluence-questions/confluence-help-{i+1000}/qaq-p/{i+300000}",
                'rovo': f"https://community.atlassian.com/t5/Rovo/rovo-discussion-{i+1000}/qaq-p/{i+400000}",
                'announcements': f"https://community.atlassian.com/t5/Announcements/announcement-{i+1000}/ba-p/{i+500000}"
            }
            
            post = {
                "title": title,
                "content": content,
                "author": author, 
                "category": category,
                "url": realistic_urls.get(category, f"https://community.atlassian.com/t5/{category}/post-{i+1000}"),
                "excerpt": content[:100] + "..." if len(content) > 100 else content,
                "date": post_date
            }
            
            posts.append(post)
            
        return posts
    
    async def populate_demo_data(self):
        """Populate database with realistic demo data"""
        print("🎭 Generating realistic demo data...")
        
        # Generate posts
        posts = await self.generate_realistic_posts(50)
        
        # Save to database
        saved_count = 0
        for post_data in posts:
            try:
                saved_post = await self.db_ops.create_or_update_post(post_data)
                if saved_post:
                    saved_count += 1
                    
                    # Add some sentiment analysis to make it realistic
                    if random.random() > 0.4:  # 60% get analyzed
                        sentiment_score = random.uniform(-0.8, 0.8)
                        if sentiment_score > 0.2:
                            sentiment_label = "positive"
                        elif sentiment_score < -0.2:
                            sentiment_label = "negative" 
                        else:
                            sentiment_label = "neutral"
                            
                        await self.db_ops.update_post_sentiment(
                            saved_post.id, sentiment_score, sentiment_label
                        )
                        
            except Exception as e:
                print(f"Error saving post: {e}")
                
        print(f"✅ Generated {saved_count} realistic demo posts!")
        return saved_count
    
    async def simulate_live_activity(self):
        """Simulate ongoing community activity"""
        print("🔄 Simulating live community activity...")
        
        # Add a few new posts to simulate real-time activity
        new_posts = await self.generate_realistic_posts(5)
        
        saved_count = 0
        for post_data in new_posts:
            # Make timestamps very recent (last few hours)
            post_data["date"] = datetime.now() - timedelta(hours=random.randint(0, 6))
            
            try:
                saved_post = await self.db_ops.create_or_update_post(post_data)
                if saved_post:
                    saved_count += 1
                    
                    # Quick sentiment analysis
                    if "issue" in post_data["title"].lower() or "problem" in post_data["title"].lower():
                        sentiment_score = random.uniform(-0.6, -0.1)
                        sentiment_label = "negative"
                    elif "great" in post_data["content"].lower() or "thanks" in post_data["content"].lower():
                        sentiment_score = random.uniform(0.1, 0.7)
                        sentiment_label = "positive"
                    else:
                        sentiment_score = random.uniform(-0.1, 0.1)
                        sentiment_label = "neutral"
                        
                    await self.db_ops.update_post_sentiment(
                        saved_post.id, sentiment_score, sentiment_label
                    )
                    
            except Exception as e:
                print(f"Error saving post: {e}")
                
        print(f"✅ Added {saved_count} new posts to simulate live activity!")
        return saved_count

async def main():
    """Run demo data generation"""
    generator = DemoDataGenerator()
    
    # Clear existing demo data first
    print("🧹 Clearing existing data...")
    await generator.db_ops.delete_all_posts()
    
    # Generate fresh demo data
    await generator.populate_demo_data()
    
    # Add some live activity
    await generator.simulate_live_activity()
    
    print("🎉 Demo data generation complete!")
    
    # Show summary
    total_posts = await generator.db_ops.get_posts_count()
    recent_posts = await generator.db_ops.get_recent_posts_count(hours=24)
    
    print(f"📊 Summary:")
    print(f"   Total Posts: {total_posts}")
    print(f"   Posts Last 24h: {recent_posts}")
    print(f"   Dashboard ready at: http://localhost:3000")

if __name__ == "__main__":
    asyncio.run(main())