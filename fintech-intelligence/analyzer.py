import json
import re
import os
import anthropic

client = anthropic.AsyncAnthropic()
MODEL = "claude-sonnet-4-5"


def _extract_json(text: str) -> dict | list:
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"[\[\{][\s\S]*[\]\}]", text)
    if not match:
        raise ValueError("No JSON found in response")
    return json.loads(match.group())


async def _ask_claude(prompt: str, max_tokens: int = 4000) -> dict | list:
    response = await client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    return _extract_json(text)


def _competitors_str(raw: list[dict]) -> str:
    names = list({r.get("competitor", "") for r in raw if r.get("competitor")})
    return ", ".join(names) if names else "GCash, Maya, Maribank, Salmon, Billease, HomeCredit"


async def analyze_meta_ads(raw_ads: list[dict]) -> dict:
    competitors = _competitors_str(raw_ads)
    prompt = (
        "You are a senior fintech marketing analyst for the Philippines. "
        f"Analyze the Meta (Facebook/Instagram) ad strategies of: {competitors}. "
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","active_ads_count":"estimate",'
        '"main_message":"core message","target_audience":"who","tone":"friendly",'
        '"offers":["offer1"],"cta":"action","insight":"2 sentences","signal":"bullish",'
        '"sample_ad_url":null}],"patterns":["p1","p2","p3"],'
        '"takeaway":"overall strategic takeaway"}'
    )
    try:
        return await _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_websites(raw_sites: list[dict]) -> dict:
    competitors = _competitors_str(raw_sites)
    prompt = (
        "You are a fintech product analyst for the Philippines. "
        f"Analyze products, rates, fees, promos of: {competitors}. "
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","products":["p1","p2"],'
        '"key_rates":["rate1"],"current_promos":["promo1"],'
        '"positioning":"how positioned","target_segment":"who",'
        '"insight":"2 sentences","signal":"bullish","url":"website"}],'
        '"patterns":["p1","p2"],"takeaway":"overall takeaway"}'
    )
    try:
        return await _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_app_store(raw_apps: list[dict]) -> dict:
    competitors = _competitors_str(raw_apps)
    prompt = (
        "You are a fintech product analyst for the Philippines. "
        f"Analyze Google Play ratings and user sentiment for: {competitors}. "
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","rating":4.2,'
        '"rating_signal":"bullish","top_complaints":["c1","c2"],'
        '"top_praises":["p1","p2"],"recent_update":"what changed",'
        '"insight":"2 sentences","signal":"bullish"}],'
        '"patterns":["p1","p2"],"takeaway":"overall takeaway"}'
    )
    try:
        return await _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def analyze_news(raw_news: list[dict]) -> dict:
    competitors = _competitors_str(raw_news)
    prompt = (
        "You are a fintech industry analyst for the Philippines. "
        f"Summarize recent news and developments for: {competitors}. "
        "Return ONLY raw JSON, no markdown: "
        '{"findings":[{"competitor":"name","headline":"headline text",'
        '"summary":"2 sentences","sentiment":"positive","signal":"bullish",'
        '"url":null,"date":"approximate date"}],'
        '"patterns":["p1","p2"],"takeaway":"overall takeaway"}'
    )
    try:
        return await _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Error: {e}"}


async def generate_recommendations(all_sections: dict, competitors: list[str]) -> dict:
    comp_str = ", ".join(competitors)
    meta = all_sections.get("meta_ads", {}).get("takeaway", "N/A")
    web = all_sections.get("websites", {}).get("takeaway", "N/A")
    app = all_sections.get("app_store", {}).get("takeaway", "N/A")
    news = all_sections.get("news", {}).get("takeaway", "N/A")
    prompt = (
        f"You are a senior fintech strategy consultant for Philippines. "
        f"Competitors: {comp_str}. "
        f"Ads: {meta}. Products: {web}. Apps: {app}. News: {news}. "
        "Return ONLY raw JSON, no markdown: "
        '{"competitive_landscape":"2-3 sentences",'
        '"biggest_threats":[{"competitor":"name","threat":"why dangerous","level":"high"}],'
        '"opportunities":[{"opportunity":"gap","rationale":"why now"}],'
        '"recommendations":[{"action":"what to do","priority":"high","rationale":"why"}],'
        '"watch_list":["thing1","thing2","thing3"]}'
    )
    try:
        return await _ask_claude(prompt)
    except Exception as e:
        return {"competitive_landscape": f"Error: {e}", "recommendations": []}
