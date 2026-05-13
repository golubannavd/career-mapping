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


def _ask_claude(prompt: str, use_web_search: bool = False, max_tokens: int = 4000) -> dict | list:
    tools = [{"type": "web_search_20250305", "name": "web_search"}] if use_web_search else []
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    if tools:
        kwargs["tools"] = tools
    response = client.messages.create(**kwargs)
    text_parts = [b.text for b in response.content if hasattr(b, "text")]
    return _extract_json("\n".join(text_parts))


def _safe_ascii(s: str) -> str:
    """Strip non-ASCII to avoid codec errors in HTTP requests."""
    return s.encode("ascii", errors="ignore").decode("ascii")


def _errors_from_raw(items: list[dict]) -> list[str]:
    return list({_safe_ascii(str(i["error"])) for i in items if "error" in i})


def analyze_meta_ads(raw_ads: list[dict]) -> dict:
    errors = _errors_from_raw(raw_ads)
    ads = [a for a in raw_ads if "error" not in a]

    if not ads:
        # Fallback: use Claude web search
        competitors = list({a.get("competitor", "") for a in raw_ads if a.get("competitor")})
        error_msg = "; ".join(errors[:2]) if errors else "no data returned"
        prompt = f"""You are a fintech marketing analyst for the Philippines.

Apify scraping failed ({error_msg}). Use web search to find current Meta/Facebook ads
from these Philippine fintech companies: {', '.join(competitors)}.
Search for their Facebook Ads Library entries, active campaigns, and promotions.

Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "active_ads_count": 0,
      "main_message": "core offer or message",
      "target_audience": "who they target",
      "tone": "urgent|friendly|professional|aggressive",
      "offers": ["specific offers, rates, promos"],
      "cta": "call to action",
      "insight": "2 sentences on strategy",
      "signal": "bullish|bearish|neutral|watch",
      "sample_ad_url": "url or null"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2", "pattern 3"],
  "data_source": "web_search_fallback",
  "takeaway": "overall strategic takeaway"
}}"""
        try:
            result = _ask_claude(prompt, use_web_search=True)
            if isinstance(result, dict):
                result["_scrape_errors"] = errors
            return result
        except Exception as e:
            return {"findings": [], "takeaway": f"Scraping failed: {error_msg}. Web search fallback also failed: {e}", "_scrape_errors": errors}

    ads_text = json.dumps(ads, ensure_ascii=False, indent=2)
    prompt = f"""You are a fintech marketing analyst for the Philippines.

Analyze these Meta Ads Library entries from Philippine fintech competitors:
{ads_text}

Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "active_ads_count": 0,
      "main_message": "core offer or message",
      "target_audience": "who they target",
      "tone": "urgent|friendly|professional|aggressive",
      "offers": ["specific offers, rates, promos"],
      "cta": "call to action",
      "insight": "2 sentences on strategy",
      "signal": "bullish|bearish|neutral|watch",
      "sample_ad_url": "url or null"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2", "pattern 3"],
  "takeaway": "overall strategic takeaway"
}}"""
    try:
        result = _ask_claude(prompt)
        if isinstance(result, dict) and errors:
            result["_scrape_errors"] = errors
        return result
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}", "_scrape_errors": errors}


def analyze_websites(raw_sites: list[dict]) -> dict:
    errors = _errors_from_raw(raw_sites)
    sites = [s for s in raw_sites if "error" not in s]

    if not sites:
        competitors = list({s.get("competitor", "") for s in raw_sites if s.get("competitor")})
        error_msg = "; ".join(errors[:2]) if errors else "no data returned"
        prompt = f"""You are a fintech product analyst for the Philippines.

Apify scraping failed ({error_msg}). Use web search to research the current
products, interest rates, fees, and promotions of: {', '.join(competitors)}.
Visit their websites and extract key product details.

Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "products": ["product 1", "product 2"],
      "key_rates": ["rate info", "fee info"],
      "current_promos": ["promo 1"],
      "positioning": "how they position themselves",
      "target_segment": "who they target",
      "insight": "2 sentences on product strategy",
      "signal": "bullish|bearish|neutral|watch",
      "url": "their website url"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "data_source": "web_search_fallback",
  "takeaway": "overall product and positioning takeaway"
}}"""
        try:
            result = _ask_claude(prompt, use_web_search=True)
            if isinstance(result, dict):
                result["_scrape_errors"] = errors
            return result
        except Exception as e:
            return {"findings": [], "takeaway": f"Scraping failed: {error_msg}. Fallback failed: {e}", "_scrape_errors": errors}

    sites_text = json.dumps(
        [{"competitor": s["competitor"], "url": s["url"], "text": s["text"][:2000]} for s in sites],
        ensure_ascii=False, indent=2,
    )
    prompt = f"""You are a fintech product analyst for the Philippines.
Analyze these competitor website contents:
{sites_text}

Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "products": ["product 1", "product 2"],
      "key_rates": ["rate info", "fee info"],
      "current_promos": ["promo 1"],
      "positioning": "how they position themselves",
      "target_segment": "who they target",
      "insight": "2 sentences on product strategy",
      "signal": "bullish|bearish|neutral|watch",
      "url": "string"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "takeaway": "overall takeaway"
}}"""
    try:
        result = _ask_claude(prompt)
        if isinstance(result, dict) and errors:
            result["_scrape_errors"] = errors
        return result
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}", "_scrape_errors": errors}


def analyze_app_store(raw_apps: list[dict]) -> dict:
    errors = _errors_from_raw(raw_apps)
    apps = [a for a in raw_apps if "error" not in a]

    if not apps:
        competitors = list({a.get("competitor", "") for a in raw_apps if a.get("competitor")})
        error_msg = "; ".join(errors[:2]) if errors else "no data returned"
        prompt = f"""You are a fintech product analyst for the Philippines.

Apify scraping failed ({error_msg}). Use web search to find current Google Play
ratings, review counts, recent user complaints and praises for: {', '.join(competitors)}.
Search for "[competitor] app review Philippines" and their Google Play pages.

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
      "insight": "2 sentences on user sentiment",
      "signal": "bullish|bearish|neutral|watch"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "data_source": "web_search_fallback",
  "takeaway": "overall app quality and sentiment takeaway"
}}"""
        try:
            result = _ask_claude(prompt, use_web_search=True)
            if isinstance(result, dict):
                result["_scrape_errors"] = errors
            return result
        except Exception as e:
            return {"findings": [], "takeaway": f"Scraping failed: {error_msg}. Fallback failed: {e}", "_scrape_errors": errors}

    apps_text = json.dumps(apps, ensure_ascii=False, indent=2)
    prompt = f"""You are a fintech product analyst.
Analyze these App Store / Google Play data for Philippine fintech apps:
{apps_text}

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
      "insight": "2 sentences on user sentiment",
      "signal": "bullish|bearish|neutral|watch"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "takeaway": "overall app quality and sentiment takeaway"
}}"""
    try:
        result = _ask_claude(prompt)
        if isinstance(result, dict) and errors:
            result["_scrape_errors"] = errors
        return result
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}", "_scrape_errors": errors}


def analyze_news(raw_news: list[dict]) -> dict:
    errors = _errors_from_raw(raw_news)
    news = [n for n in raw_news if "error" not in n]

    if not news:
        competitors = list({n.get("competitor", "") for n in raw_news if n.get("competitor")})
        error_msg = "; ".join(errors[:2]) if errors else "no data returned"
        prompt = f"""You are a fintech industry analyst for the Philippines.

Apify scraping failed ({error_msg}). Use web search to find news from the past 2 weeks
about these Philippine fintech companies: {', '.join(competitors)}.
Search Philippine media: Rappler, Inquirer, BusinessWorld, CNN Philippines, Philstar.

Return ONLY raw JSON:
{{
  "findings": [
    {{
      "competitor": "string",
      "headline": "string",
      "summary": "2 sentences",
      "sentiment": "positive|negative|neutral",
      "signal": "bullish|bearish|neutral|watch",
      "url": "article url or null",
      "date": "string"
    }}
  ],
  "patterns": ["pattern 1", "pattern 2"],
  "data_source": "web_search_fallback",
  "takeaway": "overall news sentiment and industry direction"
}}"""
        try:
            result = _ask_claude(prompt, use_web_search=True)
            if isinstance(result, dict):
                result["_scrape_errors"] = errors
            return result
        except Exception as e:
            return {"findings": [], "takeaway": f"Scraping failed: {error_msg}. Fallback failed: {e}", "_scrape_errors": errors}

    news_text = json.dumps(news, ensure_ascii=False, indent=2)
    prompt = f"""You are a fintech industry analyst for the Philippines.
Analyze these recent news mentions:
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
  "takeaway": "overall news sentiment and industry direction"
}}"""
    try:
        result = _ask_claude(prompt)
        if isinstance(result, dict) and errors:
            result["_scrape_errors"] = errors
        return result
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}", "_scrape_errors": errors}


def generate_recommendations(all_sections: dict, competitors: list[str]) -> dict:
    summary = {s: data.get("takeaway", "") for s, data in all_sections.items()}
    prompt = f"""You are a senior fintech strategy consultant for the Philippines market.

Based on this competitive intelligence for {', '.join(competitors)}:

Meta Ads: {summary.get('meta_ads', 'N/A')}
Websites: {summary.get('websites', 'N/A')}
App Store: {summary.get('app_store', 'N/A')}
News: {summary.get('news', 'N/A')}

Return ONLY raw JSON:
{{
  "competitive_landscape": "2-3 sentences on the overall competitive situation",
  "biggest_threats": [
    {{"competitor": "string", "threat": "what makes them dangerous", "level": "high|medium|low"}}
  ],
  "opportunities": [
    {{"opportunity": "specific market gap", "rationale": "why this is an opportunity"}}
  ],
  "recommendations": [
    {{"action": "specific action to take", "priority": "high|medium|low", "rationale": "why"}}
  ],
  "watch_list": ["thing to monitor 1", "thing to monitor 2", "thing to monitor 3"]
}}"""
    try:
        return _ask_claude(prompt, use_web_search=False)
    except Exception as e:
        return {"competitive_landscape": f"Analysis error: {e}", "recommendations": []}
