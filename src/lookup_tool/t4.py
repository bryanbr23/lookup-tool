import requests

api_key = "8dab5b9e72c848c28473210df7f812fd"
query = "Apple Inc"

url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}"
response = requests.get(url)
articles = response.json().get("articles", [])

for article in articles[:5]:
    print(f"{article['title']} - {article['url']}")
