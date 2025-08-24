#!/usr/bin/env python3
"""
Quick API test script to debug response structures
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import asyncio
from database.operations import DatabaseOperations

async def test_critical_issues():
    """Test critical issues endpoint logic"""
    print("=== Testing Critical Issues Logic ===")
    
    try:
        db_ops = DatabaseOperations()
        recent_posts = db_ops.get_recent_posts(limit=50, days=7)
        
        print(f"Found {len(recent_posts)} recent posts")
        
        # Simple heuristic-based categorization
        critical_issues = []
        for post in recent_posts:
            # Look for error/issue keywords in title
            title_lower = post.get('title', '').lower()
            if any(keyword in title_lower for keyword in ['error', 'bug', 'broken', 'failed', 'issue', 'problem']):
                critical_issues.append({
                    'issue_title': post.get('title'),
                    'severity': 'high' if any(word in title_lower for word in ['critical', 'urgent', 'broken']) else 'medium',
                    'report_count': 1,
                    'affected_products': [post.get('category', 'unknown')],
                    'first_reported': post.get('date').isoformat() if post.get('date') else None,
                    'latest_report': post.get('date').isoformat() if post.get('date') else None,
                    'business_impact': 'workflow_broken' if 'broken' in title_lower else 'productivity_loss',
                    'sample_posts': [
                        {
                            'title': post.get('title'),
                            'url': post.get('url', '#'),
                            'author': post.get('author', 'Unknown')
                        }
                    ],
                    'resolution_urgency': 'high' if any(word in title_lower for word in ['critical', 'urgent']) else 'medium'
                })
        
        print(f"Found {len(critical_issues)} critical issues")
        
        if critical_issues:
            print("\nFirst critical issue:")
            print(critical_issues[0])
        
        return critical_issues[:10]
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []

async def test_database_connection():
    """Test basic database connectivity"""
    print("\n=== Testing Database Connection ===")
    
    try:
        from database.connection import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) as count FROM posts"))
            total_posts = result.fetchone()[0]
            print(f"✅ Database connected - {total_posts} total posts")
            
            # Test enhanced columns
            result = conn.execute(text("""
                SELECT id, title, enhanced_category, has_screenshots, business_value 
                FROM posts 
                LIMIT 3
            """))
            sample_posts = result.fetchall()
            
            print("\n✅ Enhanced columns accessible:")
            for post in sample_posts:
                print(f"  - {post.title[:50]}... (enhanced_category: {post.enhanced_category})")
            
            return True
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    async def main():
        # Test database first
        db_working = await test_database_connection()
        
        if db_working:
            # Test business intelligence
            critical_issues = await test_critical_issues()
        else:
            print("Skipping API tests due to database issues")
    
    asyncio.run(main())