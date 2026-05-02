"""Shared catalog of topics, keywords, and news sources."""

AVAILABLE_TOPICS: list[str] = [
    "world", "politics", "technology", "business", "science",
    "health", "environment", "sports", "entertainment", "finance",
    "ai", "cybersecurity", "space", "climate", "education",
]

DEFAULT_TOPICS: list[str] = ["world", "technology", "business", "science"]

AVAILABLE_KEYWORDS: list[str] = [
    "breaking", "election", "war", "economy", "inflation", "recession",
    "stock market", "artificial intelligence", "machine learning",
    "cryptocurrency", "bitcoin", "climate change", "renewable energy",
    "covid", "pandemic", "ukraine", "china", "united states", "europe",
    "middle east", "nuclear", "trade", "sanctions", "merger", "startup",
    "ipo", "layoffs", "nasa", "spacex", "cancer", "vaccine",
]

# (name, url, topics)
ALL_SOURCES: list[tuple[str, str, list[str]]] = [
    ("BBC News",            "http://feeds.bbci.co.uk/news/rss.xml",                          ["world"]),
    ("Reuters Top News",    "https://feeds.reuters.com/reuters/topNews",                     ["world"]),
    ("AP News",             "https://feeds.apnews.com/rss/apf-topnews",                      ["world"]),
    ("Al Jazeera",          "https://www.aljazeera.com/xml/rss/all.xml",                     ["world"]),
    ("The Guardian World",  "https://www.theguardian.com/world/rss",                         ["world"]),
    ("NY Times",            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",     ["world"]),
    ("Sky News World",      "https://feeds.skynews.com/feeds/rss/world.xml",                 ["world"]),
    ("Deutsche Welle",      "https://rss.dw.com/rdf/rss-en-all",                             ["world"]),
    ("France 24",           "https://www.france24.com/en/rss",                               ["world"]),
    ("NPR News",            "https://feeds.npr.org/1001/rss.xml",                            ["world"]),
    ("CBC News",            "https://www.cbc.ca/cmlink/rss-topstories",                      ["world"]),
    ("ABC News",            "https://feeds.abcnews.com/abcnews/topstories",                  ["world"]),
    ("Politico",            "https://www.politico.com/rss/politicopicks.xml",                ["politics"]),
    ("The Hill",            "https://thehill.com/feed/",                                     ["politics"]),
    ("BBC Politics",        "http://feeds.bbci.co.uk/news/politics/rss.xml",                 ["politics"]),
    ("Guardian Politics",   "https://www.theguardian.com/politics/rss",                      ["politics"]),
    ("TechCrunch",          "https://techcrunch.com/feed/",                                  ["technology"]),
    ("The Verge",           "https://www.theverge.com/rss/index.xml",                        ["technology"]),
    ("Wired",               "https://www.wired.com/feed/rss",                                ["technology"]),
    ("Ars Technica",        "https://feeds.arstechnica.com/arstechnica/index",               ["technology"]),
    ("MIT Tech Review",     "https://www.technologyreview.com/feed/",                        ["technology", "ai", "science"]),
    ("The Hacker News",     "https://feeds.feedburner.com/TheHackersNews",                   ["technology", "cybersecurity"]),
    ("ZDNet",               "https://www.zdnet.com/news/rss.xml",                            ["technology"]),
    ("VentureBeat AI",      "https://venturebeat.com/category/ai/feed/",                     ["ai", "technology"]),
    ("Financial Times",     "https://www.ft.com/rss/home",                                   ["business", "finance"]),
    ("Bloomberg Markets",   "https://feeds.bloomberg.com/markets/news.rss",                  ["business", "finance"]),
    ("WSJ World News",      "https://feeds.a.dj.com/rss/RSSWorldNews.xml",                   ["business", "world"]),
    ("Forbes",              "https://www.forbes.com/real-time/feed2/",                       ["business", "finance"]),
    ("The Economist",       "https://www.economist.com/finance-and-economics/rss.xml",       ["finance", "business"]),
    ("CNBC Top News",       "https://www.cnbc.com/id/100003114/device/rss/rss.html",         ["business", "finance"]),
    ("Nature News",         "https://www.nature.com/nature.rss",                             ["science"]),
    ("Science Daily",       "https://www.sciencedaily.com/rss/all.xml",                      ["science"]),
    ("New Scientist",       "https://www.newscientist.com/feed/home/",                       ["science"]),
    ("NASA News",           "https://www.nasa.gov/rss/dyn/breaking_news.rss",                ["science", "space"]),
    ("WHO News",            "https://www.who.int/rss-feeds/news-english.xml",                ["health"]),
    ("Medical News Today",  "https://www.medicalnewstoday.com/rss/news.xml",                 ["health"]),
    ("Guardian Environment","https://www.theguardian.com/environment/rss",                   ["environment", "climate"]),
    ("Carbon Brief",        "https://www.carbonbrief.org/feed",                              ["environment", "climate"]),
    ("BBC Sport",           "http://feeds.bbci.co.uk/sport/rss.xml",                         ["sports"]),
    ("ESPN",                "https://www.espn.com/espn/rss/news",                            ["sports"]),
    ("Variety",             "https://variety.com/feed/",                                     ["entertainment"]),
    ("Hollywood Reporter",  "https://www.hollywoodreporter.com/feed/",                       ["entertainment"]),
    ("Krebs on Security",   "https://krebsonsecurity.com/feed/",                             ["cybersecurity"]),
    ("Dark Reading",        "https://www.darkreading.com/rss.xml",                           ["cybersecurity"]),
    ("Space.com",           "https://www.space.com/feeds/all",                               ["space", "science"]),
    ("SpaceNews",           "https://spacenews.com/feed/",                                   ["space"]),
]

DEFAULT_ENABLED_SOURCES = [
    "BBC News", "Reuters Top News", "NY Times", "Sky News World",
    "TechCrunch", "The Hacker News",
]
