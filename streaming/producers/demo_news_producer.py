"""Demo News Data Producer - Generates sample AAPL news for clustering tests"""

import json
from pathlib import Path

DEMO_NEWS_DATA = [
    # Story 1: Vision Pro Launch & Expansion
    {"symbol": "AAPL", "timestamp": "2024-03-01T09:00:00Z", "title": "Apple Vision Pro Launch in US Exceeds Expectations",
     "description": "Apple's Vision Pro headset is off to a remarkably strong start in the United States, with early sales far surpassing internal targets. Pre-orders sold out in just a few hours, and retail stores reported long lines of customers eager to try the mixed-reality device.",
     "source": "TechCrunch", "url": "", "published_at": "2024-03-01T09:00:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-08T14:30:00Z", "title": "Apple Plans Vision Pro Expansion to UK and Canada by Summer",
     "description": "Apple is preparing the next phase of its Vision Pro rollout with an expansion into the UK and Canada, expected during Q2 2024. According to Bloomberg sources, Apple is finalizing distribution and training programs for retail staff.",
     "source": "Bloomberg", "url": "", "published_at": "2024-03-08T14:30:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-15T11:00:00Z", "title": "Apple Vision Pro to Launch in 8 Countries, Including China and Japan",
     "description": "Apple has officially confirmed its largest international Vision Pro rollout to date, covering eight major markets including China, Japan, Germany, and Australia. The company plans phased availability through June and July 2024.",
     "source": "Reuters", "url": "", "published_at": "2024-03-15T11:00:00Z"},
    
    # Story 2: AI Partnership Evolution
    {"symbol": "AAPL", "timestamp": "2024-03-02T10:15:00Z", "title": "Apple Reportedly in Talks with Google for Gemini AI Integration",
     "description": "Apple has reportedly initiated discussions with Google regarding the potential integration of the Gemini AI model into iOS 18. The talks center on powering next-generation AI features such as generative responses and advanced writing tools.",
     "source": "The Information", "url": "", "published_at": "2024-03-02T10:15:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-10T16:45:00Z", "title": "Apple Shifts Focus to OpenAI for iOS AI Features",
     "description": "Apple has reportedly redirected its AI partnership strategy toward OpenAI after negotiations with Google reached a stalemate over privacy terms. Apple is now in advanced discussions to bring ChatGPT-powered intelligence to iOS 18.",
     "source": "Wall Street Journal", "url": "", "published_at": "2024-03-10T16:45:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-18T13:20:00Z", "title": "Apple Announces 'Apple Intelligence' with OpenAI Partnership",
     "description": "Apple officially introduced 'Apple Intelligence', a unified suite of AI-powered features integrated into iOS 18 and macOS 15. The system leverages a partnership with OpenAI to enhance productivity and device personalization.",
     "source": "Apple Newsroom", "url": "", "published_at": "2024-03-18T13:20:00Z"},
    
    # Story 3: EU Regulatory Issues
    {"symbol": "AAPL", "timestamp": "2024-03-05T08:30:00Z", "title": "EU Fines Apple €1.8 Billion Over App Store Restrictions",
     "description": "The European Commission has imposed a landmark €1.8 billion fine on Apple for anti-competitive restrictions affecting music-streaming apps. Regulators found that Apple's anti-steering rules prevented developers from informing users about alternatives.",
     "source": "Financial Times", "url": "", "published_at": "2024-03-05T08:30:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-12T15:00:00Z", "title": "Apple Plans Appeal Against EU Fine, Calls Ruling 'Unjustified'",
     "description": "Apple has announced its intention to appeal the European Commission's €1.8 billion fine, arguing that the decision fundamentally misinterprets the competitive landscape of the music-streaming market.",
     "source": "CNBC", "url": "", "published_at": "2024-03-12T15:00:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-20T09:45:00Z", "title": "Apple Announces App Store Changes in EU to Comply with DMA",
     "description": "Apple has introduced sweeping App Store changes across the European Union to comply with Digital Markets Act requirements. Updates include support for alternative payment systems and app sideloading.",
     "source": "TechCrunch", "url": "", "published_at": "2024-03-20T09:45:00Z"},
    
    # Story 4: India Manufacturing Expansion
    {"symbol": "AAPL", "timestamp": "2024-03-03T12:00:00Z", "title": "Apple Supplier Foxconn Invests $1.5B in India Manufacturing",
     "description": "Foxconn has announced a major $1.5 billion investment to expand iPhone production capacity in India, reflecting Apple's strategy to diversify manufacturing beyond China.",
     "source": "Reuters", "url": "", "published_at": "2024-03-03T12:00:00Z"},
    {"symbol": "AAPL", "timestamp": "2024-03-14T10:30:00Z", "title": "Apple to Produce 25% of iPhones in India by 2025, Sources Say",
     "description": "Apple is accelerating its manufacturing expansion in India, aiming to produce one-quarter of all iPhones in the country by 2025, supported by Foxconn, Pegatron, and Tata Electronics.",
     "source": "Bloomberg", "url": "", "published_at": "2024-03-14T10:30:00Z"}
]


def save_demo_news_data(output_dir: str = "./demo_data"):
    """Save demo news data to CSV and JSON files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    sorted_data = sorted(DEMO_NEWS_DATA, key=lambda x: x['timestamp'])
    
    # Save JSON
    with open(output_path / "AAPL_news.json", 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, indent=2)
    
    # Save CSV for Pathway
    with open(output_path / "AAPL_news.csv", 'w', encoding='utf-8') as f:
        f.write("symbol,timestamp,title,description,source,url,published_at\n")
        for a in sorted_data:
            f.write(f'"{a["symbol"]}","{a["timestamp"]}","{a["title"].replace(chr(34), chr(34)+chr(34))}","{a["description"].replace(chr(34), chr(34)+chr(34))}","{a["source"]}","{a["url"]}","{a["published_at"]}"\n')
    
    print(f"Saved {len(sorted_data)} articles to {output_path}")
    return {"symbol": "AAPL", "total_articles": len(sorted_data)}


if __name__ == "__main__":
    save_demo_news_data()
