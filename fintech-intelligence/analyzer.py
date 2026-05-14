import json
import re
import os
import asyncio
import anthropic

# Strip any hidden non-ASCII characters that copy-paste can introduce into the key
_raw_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
_clean_key = _raw_key.encode("ascii", errors="ignore").decode("ascii")
client = anthropic.AsyncAnthropic(api_key=_clean_key)
MODEL = "claude-sonnet-4-5"

_NO_HALLUCINATE = (
    "CRITICAL: Only report information you actually find in web search results. "
    "Do NOT use training knowledge or make up data. "
    "If you cannot find real data for a competitor, set signal to 'unknown' and note 'no data found in search'. "
)


def _extract_json(text: str) -> dict | list:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"[\[\{][\s\S]*[\]\}]", text)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group())


async def _ask_claude_with_search(prompt: str, max_uses: int = 3, max_tokens: int = 3000) -> dict | list:
    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}],
                messages=[{"role": "user", "content": prompt}],
            )
            text = next(
                (block.text for block in reversed(response.content) if hasattr(block, "text")),
                None,
            )
            if not text:
                raise ValueError("No text block in response")
            return _extract_json(text)
        except anthropic.RateLimitError:
            if attempt == 2:
                raise
            await asyncio.sleep(20 * (attempt + 1))


def _competitors_str(raw: list[dict]) -> str:
    names = list({r.get("competitor", "") for r in raw if r.get("competitor")})
    return ", ".join(names) if names else "GCash, Maya, Maribank, Salmon, Billease, HomeCredit"


async def analyze_meta_ads(raw_ads: list[dict]) -> dict:
    competitors = _competitors_str(raw_ads)
    prompt = (
        f"Search the Meta Ads Library (facebook.com/ads/library) and the web for current Facebook and Instagram ads "
        f"from these Philippines fintech companies: {competitors}. "
        "Search each company name + 'Philippines' + 'Facebook ads' or 'Instagram ads'. "
        + _NO_HALLUCINATE +
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","active_ads_count":"real number or unknown",'
        '"main_message":"found message or null","target_audience":"found or null","tone":"found or null",'
        '"offers":["real offers found"],"cta":"found or null","insight":"what search actually found","signal":"bullish|bearish|neutral|unknown",'
        '"sample_ad_url":"real url or null"}],"patterns":["only patterns found in search results"],'
        '"takeaway":"summary based only on found data, state if data was limited"}'
    )
    try:
        return await _ask_claude_with_search(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_websites(raw_sites: list[dict]) -> dict:
    competitors = _competitors_str(raw_sites)
    # Include any scraped text if available
    scraped = [
        f"{s['competitor']}: {s.get('text','')[:500]}"
        for s in raw_sites if s.get('text') and not s.get('error')
    ]
    scraped_ctx = (" Scraped website content: " + " | ".join(scraped)) if scraped else ""
    prompt = (
        f"Search the official websites and recent articles for these Philippines fintech companies: {competitors}. "
        "Find their current loan/savings rates, active promotions, product lineup, and positioning."
        + scraped_ctx + " "
        + _NO_HALLUCINATE +
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","products":["real products found"],'
        '"key_rates":["real rates found e.g. 6% p.a."],"current_promos":["real active promo or none found"],'
        '"positioning":"found positioning or null","target_segment":"found or null",'
        '"insight":"what search actually found","signal":"bullish|bearish|neutral|unknown","url":"official site url"}],'
        '"patterns":["only real patterns from search"],"takeaway":"based only on found data"}'
    )
    try:
        return await _ask_claude_with_search(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_app_store(raw_apps: list[dict]) -> dict:
    competitors = _competitors_str(raw_apps)
    # Include any scraped app data if available
    scraped = [
        f"{a['competitor']}: rating {a.get('rating','?')}, reviews: {[r.get('text','') for r in a.get('recent_reviews',[])[:2]]}"
        for a in raw_apps if not a.get('error') and a.get('rating')
    ]
    scraped_ctx = (" Scraped Play Store data: " + " | ".join(scraped)) if scraped else ""
    prompt = (
        f"Search Google Play Store for the apps of these Philippines fintech companies: {competitors}. "
        "Find their current ratings, number of reviews, recent user complaints and praises, and latest app updates."
        + scraped_ctx + " "
        + _NO_HALLUCINATE +
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","rating":"real number from Play Store or null",'
        '"rating_signal":"bullish|bearish|neutral|unknown","top_complaints":["real complaints from reviews"],'
        '"top_praises":["real praises from reviews"],"recent_update":"real recent update info or null",'
        '"insight":"what search actually found","signal":"bullish|bearish|neutral|unknown"}],'
        '"patterns":["only real patterns"],"takeaway":"based only on found data"}'
    )
    try:
        return await _ask_claude_with_search(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_news(raw_news: list[dict]) -> dict:
    competitors = _competitors_str(raw_news)
    prompt = (
        f"Search the web for news published in the last 3 days about these Philippines fintech companies: {competitors}. "
        "Find real articles: product launches, funding rounds, partnerships, regulatory updates, app changes. "
        + _NO_HALLUCINATE +
        "Return ONLY raw JSON with real article URLs and dates, no markdown: "
        '{"findings":[{"competitor":"name","headline":"real headline from article",'
        '"summary":"2 sentences about what actually happened","sentiment":"positive|negative|neutral","signal":"bullish|bearish|neutral",'
        '"url":"real article url","date":"actual date e.g. May 14 2026"}],'
        '"patterns":["only real patterns"],"takeaway":"based only on found articles, note if few results"}'
    )
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{"role": "user", "content": prompt}],
        )
        text = next(
            (block.text for block in reversed(response.content) if hasattr(block, "text")),
            None,
        )
        if not text:
            raise ValueError("No text block in response")
        return _extract_json(text)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_social_posts(raw_posts: list[dict]) -> dict:
    competitors = _competitors_str(raw_posts)
    captions = [
        f"{p.get('competitor')}: {(p.get('caption') or '')[:150]}"
        for p in raw_posts if p.get('caption') and not p.get('error')
    ][:20]
    scraped_ctx = (" Scraped post captions: " + " | ".join(captions)) if captions else ""
    prompt = (
        f"Search Instagram and Facebook for recent posts from these Philippines fintech companies: {competitors}. "
        "Search each company's official Instagram handle and Facebook page for recent content, campaigns, and engagement."
        + scraped_ctx + " "
        + _NO_HALLUCINATE +
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","posting_frequency":"found or unknown",'
        '"content_themes":["only themes actually found"],"tone":"found or unknown",'
        '"engagement_style":"found or unknown","top_performing_content":"real example found or null",'
        '"insight":"what search actually found","signal":"bullish|bearish|neutral|unknown"}],'
        '"patterns":["only real patterns found"],"takeaway":"based only on found data"}'
    )
    try:
        return await _ask_claude_with_search(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def generate_recommendations(all_sections: dict, competitors: list[str]) -> dict:
    comp_str = ", ".join(competitors)
    meta = all_sections.get("meta_ads", {}).get("takeaway", "N/A")
    web = all_sections.get("websites", {}).get("takeaway", "N/A")
    app = all_sections.get("app_store", {}).get("takeaway", "N/A")
    news = all_sections.get("news", {}).get("takeaway", "N/A")
    social = all_sections.get("social", {}).get("takeaway", "N/A")
    prompt = (
        f"You are a senior fintech strategy consultant for Philippines. "
        f"Based ONLY on this verified research data — "
        f"Ads: {meta}. Products: {web}. Apps: {app}. News: {news}. Social: {social}. "
        f"Competitors analyzed: {comp_str}. "
        "Do NOT add information beyond what is in the data above. "
        "Return ONLY raw JSON, no markdown: "
        '{"competitive_landscape":"2-3 sentences based only on the data above",'
        '"biggest_threats":[{"competitor":"name","threat":"specific threat from data","level":"high|medium|low"}],'
        '"opportunities":[{"opportunity":"specific gap from data","rationale":"evidence from data"}],'
        '"recommendations":[{"action":"strategic action","priority":"high|medium|low","rationale":"cite which data supports this","horizon":"6-12 months"}],'
        '"tactical_actions":[{"action":"specific tactic","channel":"Meta Ads|App Store|Pricing|Product|Content","timeline":"this week|30 days|90 days","expected_impact":"measurable outcome"}],'
        '"watch_list":["specific things to monitor from findings"]}'
    )
    try:
        return await _ask_claude_with_search(prompt, max_uses=3)
    except Exception as e:
        return {"competitive_landscape": f"Error: {e}", "recommendations": []}
