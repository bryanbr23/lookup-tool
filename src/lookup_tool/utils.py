# ========== app/utils.py ==========

import os, requests
from bs4 import BeautifulSoup
from app.openai_client import summarize_with_openai

def crawl_website(company_name):
    try:
        if company_name.lower() == "msft":
            url = "https://www.microsoft.com"
        else:
            url = f"https://www.{company_name.lower()}.com"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.get_text()

        officers = ["John Doe (CEO)", "Jane Smith (CFO)"]  # TODO: Parse real data if possible
        description = f"{company_name} is a leading company in its sector."
        return content, officers, description
    except Exception as e:
        print(f"[crawl_website] Error fetching website for {company_name}: {e}")
        return None

def download_sec_filings(company_name):
    # Placeholder: Simulate SEC filing retrieval
    filings = ["10-Q quarterly report text...", "10-K annual report text..."]
    return filings

def summarize_documents(documents):
    # Updated to use OpenAI for summarization
    summaries = []
    for doc in documents:
        summary = summarize_with_openai(doc[:3000], os.getenv("OPENAI_API_KEY"))
        summaries.append(summary)
    return summaries
    # Placeholder summarization logic
    return ["Summary of " + doc[:50] + "..." for doc in documents]

def save_documents(company_name, facts):
    os.makedirs(f"data/{company_name}", exist_ok=True)
    for key, value in facts.items():
        with open(f"data/{company_name}/{key}.txt", "w", encoding="utf-8") as f:
            if isinstance(value, list):
                f.write("\n".join(value))
            elif isinstance(value, dict):
                f.write("\n".join(f"{k}: {v}" for k, v in value.items()))
            else:
                f.write(str(value))
