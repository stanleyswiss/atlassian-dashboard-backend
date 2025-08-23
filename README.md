# Atlassian Community Dashboard - Backend

FastAPI backend that scrapes Atlassian Community forums, performs AI-powered sentiment analysis, and provides real-time analytics through REST APIs.

## 🛠️ Tech Stack

- **FastAPI** - High-performance async web framework
- **SQLAlchemy** - SQL toolkit and ORM
- **PostgreSQL** (production) / SQLite (development)
- **OpenAI API** - GPT-4o-mini for sentiment analysis
- **aiohttp** + **BeautifulSoup4** - Async web scraping
- **Pydantic** - Data validation

## 🚀 Quick Start

### Development
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env
uvicorn main:app --reload
```

### Production
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

## 📋 Environment Variables

Set these in Railway dashboard or `.env` file:

```bash
# Database
DATABASE_URL=postgresql://username:password@host:port/database

# OpenAI API
OPENAI_API_KEY=your_openai_api_key_here

# CORS
CORS_ORIGINS=https://your-frontend.vercel.app

# Server
PORT=8000
ENVIRONMENT=production
```

## 🌐 Deployment (Railway)

1. **Connect to GitHub** - Import your repository in Railway
2. **Add PostgreSQL Database** - Railway provides this automatically
3. **Set Environment Variables** in Railway dashboard
4. **Deploy** - Railway auto-builds and deploys

### Railway Environment Variables
```
DATABASE_URL=postgresql://... (auto-provided)
OPENAI_API_KEY=your_openai_api_key_here
CORS_ORIGINS=https://your-frontend.vercel.app
ENVIRONMENT=production
```

## 📚 API Documentation

Once running, visit:
- **API Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Health Check**: `http://localhost:8000/health`

## 🔧 Key Features

### Data Collection
- ✅ Async scraping from 5 Atlassian forums
- ✅ Real-time post extraction with modern CSS selectors
- ✅ Duplicate detection and data validation
- ✅ Rate limiting and error handling

### AI Analysis
- ✅ OpenAI GPT-4o-mini sentiment analysis
- ✅ Batch processing for efficiency
- ✅ Configurable through settings API

### APIs
- ✅ Dashboard overview with health metrics
- ✅ Posts CRUD with filtering and search
- ✅ Analytics and trending topics
- ✅ Settings management
- ✅ Background task monitoring

### Background Tasks
- ✅ Automated data collection pipeline
- ✅ Sentiment analysis queue processing
- ✅ Analytics generation
- ✅ Health monitoring

## 🏗️ Architecture

```
FastAPI App
├── API Routes (/api/*)
├── Database Layer (SQLAlchemy)
├── Services
│   ├── Web Scraper (async)
│   ├── AI Analyzer (OpenAI)
│   └── Data Processor
└── Background Scheduler
```

## 🐛 Troubleshooting

### Common Issues
- **Database connection**: Check `DATABASE_URL` format
- **CORS errors**: Verify `CORS_ORIGINS` includes your frontend URL
- **OpenAI errors**: Ensure valid `OPENAI_API_KEY`
- **Scraping issues**: Check internet connectivity and rate limits

Built with 🚀 using modern Python async patterns.