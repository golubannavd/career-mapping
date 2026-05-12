import json
import re
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"


def _extract_json(text: str) -> dict | list:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"[\[\{][\s\S]*[\]\}]", text)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group())


def _ask_claude(prompt: str, max_tokens: int = 4000) -> dict | list:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json(response.content[0].text)


def analyze_meta_ads(raw_ads: list[dict]) -> dict:
    # Filter out errors
    ads = [a for a in raw_ads if "error" not in a]
    if not ads:
        return {"findings": [], "takeaway": "No Meta Ads data available."}

    ads_text = json.dumps(ads, ensure_ascii=False, indent=2)
    prompt = f"""You are a fintech marketing analyst focused on the Philippines market.

Analyze these Meta Ads Library entries from Philippine fintech competitors:

{ads_text}

Return ONLY raw JSON (no markdown, no explanation):
{{
  "findings": [
    {{
      "competitor": "string",
      "active_ads_count": 0,
      "main_message": "core offer or message being pushed",
      "target_audience": "who they are targeting",
      "tone": "urgent|friendly|professional|aggressive",
      "offers": ["list of specific offers, rates, promos mentioned"],
      "cta": "main call to action",
      "insight": "2 sentences on what this reveals about their strategy",
      "signal": "bullish|bearish|neutral|watch",
      "sample_ad_url": "url or null"
    }}
  ],
  "patterns": ["cross-competitor pattern 1", "pattern 2", "pattern 3"],
  "takeaway": "Overall strategic takeaway about the competitive ad landscape"
}}"""

    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def analyze_websites(raw_sites: list[dict]) -> dict:
    sites = [s for s in raw_sites if "error" not in s]
    if not sites:
        return {"findings": [], "takeaway": "No website data available."}

    sites_text = json.dumps(
        [{"competitor": s["competitor"], "url": s["url"], "text": s["text"][:2000]} for s in sites],
        ensure_ascii=False, indent=2
    )
    prompt = f"""You are a fintech product analyst focused on the Philippines market.

Analyze these competitor website contents:

{sites_text}

Extract product details, interest rates, fees, promos and positioning.
Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "products": ["product 1", "product 2"],
      "key_rates": ["interest rate info", "fee info"],
      "current_promos": ["promo 1", "promo 2"],
      "positioning": "how they position themselves",
      "target_segment": "who they target",
      "insight": "2 sentences on product strategy",
      "signal": "bullish|bearish|neutral|watch",
      "url": "string"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "takeaway": "Overall product and positioning takeaway"
}}"""

    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def analyze_app_store(raw_apps: list[dict]) -> dict:
    apps = [a for a in raw_apps if "error" not in a]
    if not apps:
        return {"findings": [], "takeaway": "No App Store data available."}

    apps_text = json.dumps(apps, ensure_ascii=False, indent=2)
    prompt = f"""You are a fintech product analyst.

Analyze these App Store / Google Play data for Philippine fintech apps:

{apps_text}

Focus on ratings, user sentiment, recent issues and what users love/hate.
Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "rating": 0.0,
      "rating_signal": "bullish|bearish|neutral|watch",
      "top_complaints": ["complaint 1", "complaint 2"],
      "top_praises": ["praise 1", "praise 2"],
      "recent_update": "what changed recently",
      "insight": "2 sentences on user sentiment and product health",
      "signal": "bullish|bearish|neutral|watch"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "takeaway": "Overall app quality and user sentiment takeaway"
}}"""

    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def analyze_news(raw_news: list[dict]) -> dict:
    news = [n for n in raw_news if "error" not in n]
    if not news:
        return {"findings": [], "takeaway": "No news data available."}

    news_text = json.dumps(news, ensure_ascii=False, indent=2)
    prompt = f"""You are a fintech industry analyst focused on the Philippines.

Analyze these recent news mentions of Philippine fintech competitors:

{news_text}

Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "headline": "string",
      "summary": "2 sentences",
      "sentiment": "positive|negative|neutral",
      "signal": "bullish|bearish|neutral|watch",
      "url": "string or null",
      "date": "string"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "takeaway": "Overall news sentiment and industry direction"
}}"""

    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def generate_recommendations(all_sections: dict, competitors: list[str]) -> dict:
    summary = {
        section: data.get("takeaway", "")
        for section, data in all_sections.items()
    }
    prompt = f"""You are a senior fintech strategy consultant for the Philippines market.

Based on this competitive intelligence summary for {', '.join(competitors)}:

Meta Ads: {summary.get('meta_ads', 'N/A')}
Websites: {summary.get('websites', 'N/A')}
App Store: {summary.get('app_store', 'N/A')}
News: {summary.get('news', 'N/A')}

Provide strategic recommendations.
Return ONLY raw JSON:
{{
  "competitive_landscape": "2-3 sentences on the overall competitive situation",
  "biggest_threats": [
    {{"competitor": "string", "threat": "what makes them dangerous", "level": "high|medium|low"}}
  ],
  "opportunities": [
    {{"opportunity": "specific gap or opening in the market", "rationale": "why this is an opportunity"}}
  ],
  "recommendations": [
    {{"action": "specific action to take", "priority": "high|medium|low", "rationale": "why"}}
  ],
  "watch_list": ["thing to monitor 1", "thing to monitor 2", "thing to monitor 3"]
}}"""

    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"competitive_landscape": f"Analysis error: {e}", "recommendations": []}


def analyze_all(raw_data: dict, competitors: list[str]) -> dict:
    sections = {}
    sections["meta_ads"] = analyze_meta_ads(raw_data.get("meta_ads", []))
    sections["websites"] = analyze_websites(raw_data.get("websites", []))
    sections["app_store"] = analyze_app_store(raw_data.get("app_store", []))
    sections["news"] = analyze_news(raw_data.get("news", []))
    sections["recommendations"] = generate_recommendations(sections, competitors)
    return sections
