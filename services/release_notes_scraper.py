"""
Release Notes Scraper Service
Implements functionality from fetch_releaseNotes 2.py
"""
import requests
import json
import asyncio
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import logging

from database import get_db, ReleaseNoteOperations
from services.ai_analyzer import AIAnalyzer

logger = logging.getLogger(__name__)

class ReleaseNotesScraper:
    """Scraper for Atlassian product and marketplace app release notes"""
    
    def __init__(self, days_to_look_back: int = 7):
        self.days_to_look_back = days_to_look_back
        self.cutoff_date = datetime.now() - timedelta(days=days_to_look_back)
        
        # Configuration from original script
        self.graphql_url = "https://marketplace.atlassian.com/gateway/api/graphql"
        self.headers = {"Content-Type": "application/json"}
        
        # API URLs for Atlassian products
        self.jira_current_url = "https://api.atlassian.com/hams/1.0/public/downloads/binaryDownloads/jira-software/current"
        self.jira_archived_url = "https://api.atlassian.com/hams/1.0/public/downloads/binaryDownloads/jira-software/archived"
        self.jsm_current_url = "https://api.atlassian.com/hams/1.0/public/downloads/binaryDownloads/jira-servicedesk/current"
        self.jsm_archived_url = "https://api.atlassian.com/hams/1.0/public/downloads/binaryDownloads/jira-servicedesk/archived"
        self.confluence_current_url = "https://api.atlassian.com/hams/1.0/public/downloads/binaryDownloads/confluence/current"
        
        # List of marketplace apps to track
        self.marketplace_apps = [
            {"name": "Advanced Tables for Confluence", "id": "197"},
            {"name": "BigGantt for Jira", "id": "1213016"},
            {"name": "BigPicture Enterprise", "id": "1215158"},
            {"name": "BigPicture", "id": "1212259"},
            {"name": "Comala Document Management", "id": "142"},
            {"name": "Comala Metadata", "id": "5295"},
            {"name": "ConfiForms for Confluence", "id": "1211860"},
            {"name": "Custom Charts for Confluence", "id": "1220493"},
            {"name": "draw.io for Confluence", "id": "1210933"},
            {"name": "draw.io for Jira", "id": "1211413"},
            {"name": "Dynamic Forms for Jira", "id": "1210820"},
            {"name": "eazyBI Reports and Charts for Jira", "id": "1211051"},
            {"name": "Elements Connect for Jira", "id": "23337"},
            {"name": "Elements Copy and Sync for Jira", "id": "1211111"},
            {"name": "Enterprise Mail Handler for Jira (JEMH)", "id": "4832"},
            {"name": "Epic Roadmap for Jira (EverIT)", "id": "1220785"},
            {"name": "Extension for JSM", "id": "1212161"},
            {"name": "Gliffy Diagrams for Confluence", "id": "254"},
            {"name": "Issue Score for Jira", "id": "1220217"},
            {"name": "JSU Automation Suite for Jira", "id": "5048"},
            {"name": "Jira Email This Issue (JETI)", "id": "4977"},
            {"name": "Jira Misc Custom Fields (JMCF)", "id": "27136"},
            {"name": "Jira Misc Workflow Extensions (JMWE)", "id": "292"},
            {"name": "Jira Workflow Toolbox", "id": "29496"},
            {"name": "License Monitoring for Confluence", "id": "1225044"},
            {"name": "License Monitoring for Jira", "id": "1223852"},
            {"name": "License Optimizer for Confluence", "id": "1225045"},
            {"name": "License Optimizer for Jira", "id": "1224199"},
            {"name": "Microsoft 365 for Jira", "id": "1213138"},
            {"name": "Navitabs Navigation Macros for Confluence", "id": "28632"},
            {"name": "Numbered Headings for Confluence", "id": "16063"},
            {"name": "Power Scripts for Jira", "id": "43318"},
            {"name": "Refined for Confluence", "id": "15231"},
            {"name": "Refined for JSM", "id": "1216711"},
            {"name": "Rich Filters for Jira Dashboards", "id": "1214789"},
            {"name": "SAML SSO for Confluence", "id": "1212129"},
            {"name": "SAML SSO for Jira", "id": "1212130"},
            {"name": "STAGIL Assets", "id": "1215311"},
            {"name": "STAGIL Database Synchronizer for Jira", "id": "1217370"},
            {"name": "STAGIL Incoming Links for Confluence", "id": "1215391"},
            {"name": "STAGIL Issue Maps", "id": "1230588"},
            {"name": "STAGIL Issue Templates and Scheduler", "id": "1213893"},
            {"name": "STAGIL Navigation Menus for Confluence", "id": "1218995"},
            {"name": "STAGIL Navigation Menus for Jira", "id": "1216090"},
            {"name": "STAGIL Project Creator for Jira", "id": "1214778"},
            {"name": "STAGIL Tables", "id": "1219099"},
            {"name": "STAGIL Tasks for Confluence", "id": "1217026"},
            {"name": "STAGIL Traffic Lights for Jira", "id": "1228779"},
            {"name": "STAGIL Workflows and Fields", "id": "1220449"},
            {"name": "ScriptRunner for Confluence", "id": "1215215"},
            {"name": "ScriptRunner for Jira", "id": "6820"},
            {"name": "Scroll PDF Exporter for Confluence", "id": "7019"},
            {"name": "Structure by Tempo Jira Portfolio Management", "id": "34717"},
            {"name": "Table Filter and Charts for Confluence", "id": "27447"},
            {"name": "Teamworkx Issue Publisher for Jira", "id": "1216007"},
            {"name": "Teamworkx Issue Picker for Jira", "id": "1218048"},
            {"name": "Teamworkx Revision for Confluence", "id": "1210994"},
            {"name": "Teamworkx Push and Pull Favorites", "id": "1212516"},
            {"name": "Teamworkx Matrix for Jira", "id": "1220089"},
            {"name": "Teamworkx Connector for Jira", "id": "1222448"},
            {"name": "Teamworkx Configuration Publisher", "id": "1221516"},
            {"name": "Timesheets by Tempo", "id": "6572"},
            {"name": "Time to SLA", "id": "1211843"},
            {"name": "Timetracker for Jira (EverIT)", "id": "1211243"},
            {"name": "Xray Enterprise", "id": "1229688"},
            {"name": "Xray Test Management for Jira", "id": "1211769"}
        ]
        
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

    def fetch_application_releases(self, url: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch version history from Atlassian API"""
        try:
            logger.info(f"Fetching version history from: {url}")
            response = requests.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.info("Successfully fetched data")
                return response.json()
            else:
                logger.warning(f"Failed to fetch data. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching application releases from {url}: {e}")
            return None

    def parse_application_version_data(self, json_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse Atlassian product version data and filter by release date"""
        try:
            if not json_data:
                return []
            
            result = []
            
            for entry in json_data:
                if 'version' in entry and isinstance(entry['version'], dict):
                    version_info = entry['version']
                    
                    version_date_str = version_info.get('date')
                    if not version_date_str:
                        continue
                    
                    try:
                        # Parse ISO format date
                        parsed_date = datetime.fromisoformat(version_date_str)
                        # Convert to naive datetime for comparison
                        if parsed_date.tzinfo is not None:
                            parsed_date = parsed_date.replace(tzinfo=None)
                    except (ValueError, TypeError, AttributeError):
                        continue
                    
                    # Check if the version is newer than our cutoff
                    if parsed_date > self.cutoff_date:
                        result.append({
                            'name': version_info.get('name'),
                            'releaseNotesUrl': version_info.get('releaseNotesURL'),
                            'date': version_date_str
                        })
            
            logger.info(f"Parsed {len(result)} recent releases")
            return result
        except Exception as e:
            logger.error(f"Error parsing application version data: {e}")
            return []

    def fetch_marketplace_app_version_history(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Fetch version history from marketplace GraphQL API"""
        try:
            logger.info(f"Fetching marketplace version history for app ID {app_id}")
            
            payload = {
                "operationName": "GetMarketplaceAppVersionHistoryBFF",
                "variables": {
                    "first": 15,
                    "hosting": ["DATA_CENTER"],
                    "appId": app_id,
                    "excludeHiddenIn": "WEBSITE"
                },
                "query": """query GetMarketplaceAppVersionHistoryBFF($appId: ID!, $hosting: [AtlassianProductHostingType!], $after: String, $first: Int, $excludeHiddenIn: MarketplaceLocation) {
  marketplaceApp(appId: $appId) {
    ...MarketplaceAppVersionHistory
    __typename
  }
}

fragment MarketplaceAppVersionHistory on MarketplaceApp {
  appId
  appKey
  name
  slug
  logo {
    ...AppListingImage
    __typename
  }
  partner {
    id
    ...MarketplaceAppPartner
    __typename
  }
  productHostingOptions(excludeHiddenIn: $excludeHiddenIn)
  watchersInfo {
    isUserWatchingApp
    __typename
  }
  listingStatus
  entityStatus
  versions(
    filter: {productHostingOptions: $hosting, excludeHiddenIn: $excludeHiddenIn, visibility: null}
    first: $first
    after: $after
  ) {
    ...AppVersions
    __typename
  }
  __typename
}

fragment AppListingImage on MarketplaceListingImage {
  original {
    id
    width
    height
    __typename
  }
  highResolution {
    id
    width
    height
    __typename
  }
  __typename
}

fragment MarketplaceAppPartner on MarketplacePartner {
  name
  __typename
}

fragment AppVersions on MarketplaceAppVersionConnection {
  totalCount
  edges {
    node {
      ...VersionHistoryAppVersion
      __typename
    }
    __typename
  }
  pageInfo {
    ...AppVersionsPageInfo
    __typename
  }
  __typename
}

fragment VersionHistoryAppVersion on MarketplaceAppVersion {
  purchaseUrl
  isSupported
  licenseType {
    name
    link
    __typename
  }
  paymentModel
  buildNumber
  version
  releaseDate
  releaseSummary
  releaseNotes
  deployment {
    compatibleProducts {
      ...VersionHistoryCompatibleProduct
      __typename
    }
    __typename
  }
  highlights {
    ...VersionHighlights
    __typename
  }
  screenshots {
    ...VersionScreenshots
    __typename
  }
  __typename
}

fragment AppVersionsPageInfo on PageInfo {
  hasNextPage
  startCursor
  endCursor
  __typename
}

fragment VersionHistoryCompatibleProduct on CompatibleAtlassianProduct {
  atlassianProduct {
    id
    name
    __typename
  }
  __typename
  ... on CompatibleAtlassianDataCenterProduct {
    __typename
    minimumVersion
    maximumVersion
  }
  ... on CompatibleAtlassianServerProduct {
    __typename
    minimumVersion
    maximumVersion
  }
}

fragment VersionHighlights on MarketplaceListingHighlight {
  title
  screenshot {
    image {
      ...AppListingImage
      __typename
    }
    __typename
  }
  __typename
}

fragment VersionScreenshots on MarketplaceListingScreenshot {
  caption
  image {
    ...AppListingImage
    __typename
  }
  __typename
}"""
            }
            
            response = requests.post(self.graphql_url, headers=self.headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Successfully fetched marketplace data for app ID {app_id}")
                return response.json()
            else:
                logger.warning(f"Failed to fetch marketplace data for app ID {app_id}. Status code: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching marketplace app version history for {app_id}: {e}")
            return None

    def parse_marketplace_version_data(self, app: Dict[str, Any], data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse marketplace app version data and filter by release date"""
        try:
            if not data or 'data' not in data or not data['data'].get('marketplaceApp'):
                logger.warning(f"No valid data found for {app['name']}")
                return []
            
            filtered_versions = []
            versions = data['data']['marketplaceApp'].get('versions', {}).get('edges', [])
            
            for version in versions:
                node = version.get('node', {})
                release_date_str = node.get('releaseDate')
                
                if release_date_str:
                    try:
                        # Handle different date formats
                        try:
                            release_date = datetime.strptime(release_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                        except ValueError:
                            release_date = datetime.strptime(release_date_str, "%Y-%m-%dT%H:%M:%SZ")
                        
                        if release_date >= self.cutoff_date:
                            version_info = {
                                "product_name": app['name'],
                                "product_type": "marketplace_app",
                                "product_id": app['id'],
                                "version": node.get("version", "N/A"),
                                "build_number": node.get("buildNumber", ""),
                                "release_date": release_date,
                                "release_summary": node.get("releaseSummary", ""),
                                "release_notes": node.get("releaseNotes", ""),
                                "download_url": f"https://marketplace.atlassian.com/download/apps/{app['id']}/version/{node.get('buildNumber', '')}"
                            }
                            filtered_versions.append(version_info)
                    except Exception as e:
                        logger.error(f"Error parsing date {release_date_str}: {e}")
            
            logger.info(f"Found {len(filtered_versions)} recent versions for {app['name']}")
            return filtered_versions
        except Exception as e:
            logger.error(f"Error parsing marketplace version data for {app['name']}: {e}")
            return []

    async def scrape_all_release_notes(self) -> Dict[str, List[Dict[str, Any]]]:
        """Scrape all release notes and return organized data"""
        results = {
            'atlassian_products': [],
            'marketplace_apps': []
        }
        
        try:
            logger.info("Starting release notes scraping...")
            
            # Scrape Atlassian products
            logger.info("Scraping Jira releases...")
            jira_releases = []
            for url in [self.jira_current_url, self.jira_archived_url]:
                releases = self.fetch_application_releases(url)
                if releases:
                    jira_releases.extend(releases)
            
            if jira_releases:
                parsed_jira = self.parse_application_version_data(jira_releases)
                for release in parsed_jira:
                    release.update({
                        'product_name': 'Jira',
                        'product_type': 'atlassian_product'
                    })
                results['atlassian_products'].extend(parsed_jira)
            
            # Scrape JSM releases
            logger.info("Scraping Jira Service Management releases...")
            jsm_releases = []
            for url in [self.jsm_current_url, self.jsm_archived_url]:
                releases = self.fetch_application_releases(url)
                if releases:
                    jsm_releases.extend(releases)
            
            if jsm_releases:
                parsed_jsm = self.parse_application_version_data(jsm_releases)
                for release in parsed_jsm:
                    release.update({
                        'product_name': 'Jira Service Management',
                        'product_type': 'atlassian_product'
                    })
                results['atlassian_products'].extend(parsed_jsm)
            
            # Scrape Confluence releases
            logger.info("Scraping Confluence releases...")
            confluence_releases = self.fetch_application_releases(self.confluence_current_url)
            if confluence_releases:
                parsed_confluence = self.parse_application_version_data(confluence_releases)
                for release in parsed_confluence:
                    release.update({
                        'product_name': 'Confluence',
                        'product_type': 'atlassian_product'
                    })
                results['atlassian_products'].extend(parsed_confluence)
            
            # Scrape marketplace apps
            logger.info("Scraping marketplace apps...")
            for app in self.marketplace_apps:
                logger.info(f"Processing app: {app['name']}")
                try:
                    data = self.fetch_marketplace_app_version_history(app['id'])
                    if data:
                        filtered_versions = self.parse_marketplace_version_data(app, data)
                        results['marketplace_apps'].extend(filtered_versions)
                    
                    # Be nice to the API
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error processing app {app['name']}: {e}")
            
            logger.info(f"Scraping complete. Found {len(results['atlassian_products'])} Atlassian product releases and {len(results['marketplace_apps'])} marketplace app releases")
            return results
            
        except Exception as e:
            logger.error(f"Error during release notes scraping: {e}")
            return results

    async def store_release_notes(self, scraped_data: Dict[str, List[Dict[str, Any]]]) -> int:
        """Store scraped release notes in database with AI analysis"""
        stored_count = 0
        
        try:
            with next(get_db()) as db:
                # Process Atlassian products
                for release_data in scraped_data['atlassian_products']:
                    try:
                        # Prepare release data for database
                        db_data = {
                            'product_name': release_data['product_name'],
                            'product_type': release_data['product_type'],
                            'version': release_data['name'],
                            'release_date': datetime.fromisoformat(release_data['date']) if isinstance(release_data['date'], str) else release_data['date'],
                            'release_notes_url': release_data.get('releaseNotesUrl')
                        }
                        
                        # Store in database
                        ReleaseNoteOperations.get_or_create_release_note(db, db_data)
                        stored_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error storing Atlassian product release: {e}")
                
                # Process marketplace apps
                for release_data in scraped_data['marketplace_apps']:
                    try:
                        # Store in database
                        ReleaseNoteOperations.get_or_create_release_note(db, release_data)
                        stored_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error storing marketplace app release: {e}")
        
        except Exception as e:
            logger.error(f"Error storing release notes: {e}")
        
        logger.info(f"Stored {stored_count} release notes in database")
        return stored_count

    async def run_full_scrape(self) -> Dict[str, Any]:
        """Run complete release notes scraping and storage"""
        try:
            logger.info("Starting full release notes scrape...")
            
            # Scrape all data
            scraped_data = await self.scrape_all_release_notes()
            
            # Store in database
            stored_count = await self.store_release_notes(scraped_data)
            
            result = {
                'success': True,
                'atlassian_products_found': len(scraped_data['atlassian_products']),
                'marketplace_apps_found': len(scraped_data['marketplace_apps']),
                'total_stored': stored_count,
                'scrape_date': datetime.now().isoformat()
            }
            
            logger.info(f"Release notes scrape completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error during full release notes scrape: {e}")
            return {
                'success': False,
                'error': str(e),
                'scrape_date': datetime.now().isoformat()
            }