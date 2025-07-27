import logging
import os
import sys
import platform
from datetime import datetime
from pathlib import Path
import requests
import re

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from .agents import realtime_summary_agent
from .agent_runner import Agent, Runner

# -------------------------------
# Logging setup
# -------------------------------
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, "agent_queries.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def log_system_info(logger):
    logger.info("=" * 50)
    logger.info("SYSTEM INFORMATION")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Platform: {platform.platform()}")
    try:
        import openai
        OPENAI_VERSION = openai.__version__
    except ImportError:
        OPENAI_VERSION = "Not installed"
    logger.info(f"OpenAI SDK Version: {OPENAI_VERSION}")
    logger.info(f"Session Started: {datetime.now()}")
    logger.info("=" * 50)

# -------------------------------
# Load environment variables with better debugging
# -------------------------------
logger = setup_logging()

# Debug: Show current file path
current_file = Path(__file__).resolve()
logger.info(f"Current file: {current_file}")

# Try multiple possible locations for .env file
possible_env_paths = [
    # Project root (2 levels up from main.py)
    current_file.parents[2] / ".env",
    # One level up (in case structure is different)
    current_file.parents[1] / ".env", 
    # Same directory as main.py
    current_file.parent / ".env",
    # Current working directory
    Path.cwd() / ".env"
]

env_loaded = False
for env_path in possible_env_paths:
    logger.info(f"Checking for .env at: {env_path}")
    if env_path.exists():
        logger.info(f"Found .env file at: {env_path}")
        load_dotenv(dotenv_path=env_path)
        env_loaded = True
        break
    else:
        logger.info(f".env file not found at: {env_path}")

if not env_loaded:
    logger.warning("No .env file found in any of the expected locations")
    logger.info("Will try to load environment variables from system environment")
    # Try loading from system environment anyway
    load_dotenv()

# Load API keys
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NEWSAPI_ORG_API_KEY = os.getenv("NEWSAPI_ORG_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")  # For Google Search API
CLEARBIT_API_KEY = os.getenv("CLEARBIT_API_KEY")  # For person enrichment

# Debug: Show which keys were loaded (without revealing the actual keys)
logger.info(f"ALPHA_VANTAGE_API_KEY loaded: {'Yes' if ALPHA_VANTAGE_API_KEY else 'No'}")
logger.info(f"OPENAI_API_KEY loaded: {'Yes' if OPENAI_API_KEY else 'No'}")
logger.info(f"NEWSAPI_ORG_API_KEY loaded: {'Yes' if NEWSAPI_ORG_API_KEY else 'No'}")
logger.info(f"SERPER_API_KEY loaded: {'Yes' if SERPER_API_KEY else 'No'}")
logger.info(f"CLEARBIT_API_KEY loaded: {'Yes' if CLEARBIT_API_KEY else 'No'}")

if NEWSAPI_ORG_API_KEY:
    logger.info(f"NEWSAPI_ORG_API_KEY (first 8 chars): {NEWSAPI_ORG_API_KEY[:8]}...")

log_system_info(logger)

# -------------------------------
# FastAPI setup
# -------------------------------
app = FastAPI(
    title="Lookup Tool",
    description="Customer/Stock/Person Lookup API",
    version="0.1.0"
)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
logger.info(f"Using Templates Directory: {templates.env.loader.searchpath[0]}")

# -------------------------------
# Person Search Functions
# -------------------------------
def search_person_with_google(person_name: str, logger):
    """Search for person information using Google Search API (Serper)"""
    if not SERPER_API_KEY:
        logger.warning("Serper API key not configured for Google search")
        return []

    try:
        url = "https://google.serper.dev/search"
        payload = {
            "q": f'"{person_name}" LinkedIn OR professional OR biography OR company',
            "num": 10
        }
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        results = response.json()
        
        search_results = []
        for result in results.get("organic", []):
            search_results.append({
                "title": result.get("title", ""),
                "url": result.get("link", ""),
                "snippet": result.get("snippet", ""),
                "source": result.get("displayLink", "")
            })
        
        logger.info(f"Found {len(search_results)} search results for: {person_name}")
        return search_results
        
    except Exception as e:
        logger.error(f"Error searching with Google API: {e}")
        return []

def search_person_with_clearbit(person_name: str, logger):
    """Search for person information using Clearbit Enrichment API"""
    if not CLEARBIT_API_KEY:
        logger.warning("Clearbit API key not configured")
        return None

    try:
        # Clearbit requires email, so this is limited
        # This is more for when you have an email address
        logger.info("Clearbit requires email address for person lookup")
        return None
        
    except Exception as e:
        logger.error(f"Error with Clearbit API: {e}")
        return None

def extract_person_info_from_search(search_results: list, person_name: str, logger):
    """Extract and structure person information from search results"""
    person_info = {
        "name": person_name,
        "linkedin_profiles": [],
        "professional_info": [],
        "company_affiliations": [],
        "other_profiles": []
    }
    
    for result in search_results:
        title = result.get("title", "").lower()
        url = result.get("url", "")
        snippet = result.get("snippet", "")
        
        # Check for LinkedIn profiles
        if "linkedin.com/in/" in url:
            person_info["linkedin_profiles"].append({
                "title": result.get("title", ""),
                "url": url,
                "snippet": snippet
            })
        
        # Check for company websites or professional info
        elif any(keyword in title for keyword in ["ceo", "founder", "director", "manager", "executive", "president"]):
            person_info["professional_info"].append({
                "title": result.get("title", ""),
                "url": url,
                "snippet": snippet,
                "source": result.get("source", "")
            })
        
        # Check for company affiliations
        elif any(keyword in snippet.lower() for keyword in ["works at", "employed at", "ceo of", "founder of"]):
            person_info["company_affiliations"].append({
                "title": result.get("title", ""),
                "url": url,
                "snippet": snippet,
                "source": result.get("source", "")
            })
        
        # Other relevant profiles
        else:
            person_info["other_profiles"].append({
                "title": result.get("title", ""),
                "url": url,
                "snippet": snippet,
                "source": result.get("source", "")
            })
    
    return person_info

# -------------------------------
# NewsAPI integration
# -------------------------------
def get_recent_news(company_name: str, logger, max_articles=5):
    if not NEWSAPI_ORG_API_KEY:
        logger.warning("NewsAPI API key not configured")
        return []

    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": company_name,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": max_articles,
            "apiKey": NEWSAPI_ORG_API_KEY
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        logger.info(f"Found {len(articles)} news articles for: {company_name}")
        return [
            {
                "title": a["title"],
                "url": a["url"],
                "date": a["publishedAt"][:10],
                "source": a["source"]["name"],
                "summary": a.get("description") or a.get("content") or "No summary available."
            }
            for a in articles
        ]
    except Exception as e:
        logger.error(f"Error retrieving news from NewsAPI: {e}")
        return []

# -------------------------------
# Query Type Detection
# -------------------------------
def detect_query_type(identifier: str, logger):
    """Detect if the input is a stock ticker, company name, or person name"""
    identifier = identifier.strip()
    
    # Stock ticker detection
    if identifier.isupper() and len(identifier) <= 5 and identifier.isalpha():
        return "stock_ticker"
    
    # Person name detection (has typical name patterns)
    name_patterns = [
        r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # First Last
        r'^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+$',  # First M. Last
        r'^[A-Z][a-z]+ [A-Z][a-z]+ [A-Z][a-z]+$',  # First Middle Last
        r'^Dr\. [A-Z][a-z]+ [A-Z][a-z]+$',  # Dr. First Last
        r'^Mr\. [A-Z][a-z]+ [A-Z][a-z]+$',  # Mr. First Last
        r'^Ms\. [A-Z][a-z]+ [A-Z][a-z]+$',  # Ms. First Last
    ]
    
    for pattern in name_patterns:
        if re.match(pattern, identifier):
            return "person_name"
    
    # Check if it contains typical person name indicators
    person_indicators = ["Dr.", "Mr.", "Ms.", "Mrs.", "Prof."]
    if any(indicator in identifier for indicator in person_indicators):
        return "person_name"
    
    # If it has 2-3 capitalized words, likely a person
    words = identifier.split()
    if 2 <= len(words) <= 3 and all(word[0].isupper() for word in words if word):
        return "person_name"
    
    # Default to company name
    return "company_name"

# -------------------------------
# Enhanced Query Logic
# -------------------------------
def query_person_info(person_name: str, logger):
    """Query information about a person"""
    start_time = datetime.now()
    
    logger.info(f"Querying person information for: {person_name}")
    
    # Search for the person using Google Search
    search_results = search_person_with_google(person_name, logger)
    
    if not search_results:
        logger.warning(f"No search results found for person: {person_name}")
        return f"No information found for person: {person_name}"
    
    # Extract structured information
    person_info = extract_person_info_from_search(search_results, person_name, logger)
    
    # Use AI agent to create a comprehensive summary
    query = f"Based on the following search results, provide a comprehensive professional summary for {person_name}. Include their current role, company, background, and any notable achievements. Search results: {search_results[:5]}"
    
    agent = Agent(
        name="PersonAnalyst",
        instructions="""You are a professional researcher that provides comprehensive and respectful summaries about individuals based on publicly available information.

When summarizing a person's profile, include:
- Full name and current professional title
- Current company/organization and role
- Professional background and experience
- Education (if available)
- Notable achievements or recognition
- Industry expertise
- Contact information (only if publicly available)

Be respectful, factual, and focus on professional information. Use markdown formatting with clear headings."""
    )

    try:
        result = Runner.run_sync(agent, query)
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Person query completed in {duration:.2f} seconds")
        
        # Enhance the AI result with structured data
        enhanced_result = result.final_output + "\n\n"
        
        # Add LinkedIn profiles if found
        if person_info["linkedin_profiles"]:
            enhanced_result += "## 🔗 LinkedIn Profiles\n"
            for profile in person_info["linkedin_profiles"][:3]:
                enhanced_result += f"- [{profile['title']}]({profile['url']})\n"
                if profile['snippet']:
                    enhanced_result += f"  *{profile['snippet'][:200]}...*\n"
            enhanced_result += "\n"
        
        # Add professional information
        if person_info["professional_info"]:
            enhanced_result += "## 💼 Professional Information\n"
            for info in person_info["professional_info"][:3]:
                enhanced_result += f"- [{info['title']}]({info['url']})\n"
                if info['snippet']:
                    enhanced_result += f"  *{info['snippet'][:200]}...*\n"
            enhanced_result += "\n"
        
        return enhanced_result
        
    except Exception as e:
        logger.error(f"Person query failed: {str(e)}")
        # Fallback to basic structured information
        fallback_result = f"# {person_name}\n\n"
        
        if person_info["linkedin_profiles"]:
            fallback_result += "## LinkedIn Profiles\n"
            for profile in person_info["linkedin_profiles"][:2]:
                fallback_result += f"- [{profile['title']}]({profile['url']})\n"
        
        if person_info["professional_info"]:
            fallback_result += "\n## Professional Information\n"
            for info in person_info["professional_info"][:3]:
                fallback_result += f"- {info['title']}\n"
                if info['snippet']:
                    fallback_result += f"  {info['snippet'][:150]}...\n"
        
        return fallback_result

def query_company_info(identifier, logger):
    start_time = datetime.now()

    if identifier.isupper() and len(identifier) <= 5 and identifier.isalpha():
        query_type = "stock_ticker"
        query = f"Tell me about the company with stock ticker {identifier}."
    else:
        query_type = "company_name"
        query = f"Tell me about {identifier}."

    logger.info(f"Query Type: {query_type}")
    logger.info(f"Input: {identifier}")
    logger.info(f"Generated Query: {query}")

    agent = Agent(
        name="CompanyAnalyst",
        instructions="""You are a helpful financial assistant that provides concise and accurate responses about companies.

When answering about companies, include:
- Overview and business model
- Key products or services
- Market position and competitors
- Top strategic and AI priorities
- Notable developments or news
- Financial highlights (PE, earnings, revenue, etc.)
Use markdown headings and bullet points."""
    )

    try:
        result = Runner.run_sync(agent, query)
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Query completed in {duration:.2f} seconds")
        logger.info("RESPONSE:")
        logger.info(result.final_output)
        return result.final_output

    except Exception as e:
        logger.error(f"Agent query failed: {str(e)}")
        logger.info("Falling back to realtime_summary_agent...")
        try:
            company_data = realtime_summary_agent(identifier)
            summary_parts = [f"**Company Overview: {identifier}**"]

            if company_data.get("business_description"):
                summary_parts.append(f"**Business Description:**\n{company_data['business_description']}")
            if company_data.get("employee_count"):
                summary_parts.append(f"**Employee Count:** {company_data['employee_count']:,}")
            if company_data.get("officers"):
                summary_parts.append("**Key Officers:**")
                summary_parts.extend([f"- {officer}" for officer in company_data["officers"]])
            if company_data.get("latest_news"):
                summary_parts.append(f"**Latest News:**\n{company_data['latest_news']}")

            summary_parts.append("**AI Adoption Status:** Unknown\n")
            summary_parts.append("**Strategic Priorities:** Unknown\n")

            return "\n".join(summary_parts)

        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            return None

# -------------------------------
# Shared fetch logic
# -------------------------------
async def fetch(input_value: str):
    try:
        logger.info(f"Processing fetch for: {input_value}")
        
        # Detect query type
        query_type = detect_query_type(input_value, logger)
        logger.info(f"Detected query type: {query_type}")
        
        if query_type == "person_name":
            result = query_person_info(input_value, logger)
            # For person queries, search for news about the person
            news_items = get_recent_news(input_value, logger)
        else:
            result = query_company_info(input_value, logger)
            # For company queries, search for company news
            news_items = get_recent_news(input_value, logger)
        
        return result if result else f"No information found for: {input_value}", news_items
        
    except Exception as e:
        logger.error(f"Fetch failed: {str(e)}")
        return f"Error: {str(e)}", []

# -------------------------------
# Routes
# -------------------------------
@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "alpha_vantage_configured": bool(ALPHA_VANTAGE_API_KEY),
        "newsapi_configured": bool(NEWSAPI_ORG_API_KEY),
        "openai_configured": bool(OPENAI_API_KEY),
        "serper_configured": bool(SERPER_API_KEY),
        "clearbit_configured": bool(CLEARBIT_API_KEY)
    }

@app.post("/submit")
async def submit_form(input_value: str = Form(...)):
    try:
        input_cleaned = input_value.strip()
        if not input_cleaned:
            return {"status": "error", "message": "Input cannot be empty"}

        result, news_items = await fetch(input_cleaned)

        return {
            "status": "success",
            "input": input_cleaned,
            "result": result,
            "news": news_items,
            "query_type": detect_query_type(input_cleaned, logger)
        }

    except Exception as e:
        logger.error(f"Submit failed: {str(e)}")
        return {"status": "error", "message": f"Error: {str(e)}"}

# -------------------------------
# Entry point
# -------------------------------
def main():
    uvicorn.run("src.lookup_tool.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()