import json
import re
import os

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

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
    text = response.content[0].text
    return _extract_json(text)


def _competitors_str(raw: list[dict]) -> str:
    names = list({r.get("competitor", "") for r in raw if r.get("competitor")})
    return ", ".join(names) if names else "GCash, Maya, Maribank, Salmon, Billease, HomeCredit"


def analyze_meta_ads(raw_ads: list[dict]) -> dict:
    competitors = _competitors_str(raw_ads)
    prompt = f"""You are a senior fintech marketing analyst specializing in the Philippines market.

Analyze the current Meta (Facebook/Instagram) advertising strategies of these Philippine fintech companies: {competitors}.

Based on your knowledge of their marketing approaches, campaigns, and brand positioning, provide analysis of their ad strategies.

Return ONLY raw JSON with no markdown or explanation:
{{
  "findings": [
    {{
      "competitor": "company name",
      "active_ads_count": "estimated number or range",
      "main_message": "core marketing message they push",
      "target_audience": "who they are targeting",
      "tone": "urgent or friendly or professional or aggressive",
      "offers": ["specific offers, rates, promos they typically advertise"],
      "cta": "typical call to action",
      "insight": "2 sentences on what this reveals about their strategy",
      "signal": "bullish or bearish or neutral or watch",
      "sample_ad_url": null
    }}
  ],
  "patterns": ["cross-competitor pattern 1", "pattern 2", "pattern 3"],
  "takeaway": "Overall strategic takeaway about the competitive ad landscape in PH fintech"
}}"""
    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def analyze_websites(raw_sites: list[dict]) -> dict:
    competitors = _competitors_str(raw_sites)
    prompt = f"""You are a senior fintech product analyst specializing in the Philippines market.

Analyze the product offerings, interest rates, fees, and positioning of these Philippine fintech companies: {competitors}.

Based on your knowledge of their products and websites, provide detailed analysis.

Return ONLY raw JSON with no markdown or explanation:
{{
  "findings": [
    {{
      "competitor": "company name",
      "products": ["product 1", "product 2", "product 3"],
      "key_rates": ["interest rate info", "fee structure", "loan terms"],
      "current_promos": ["active promotion or offer"],
      "positioning": "how they position themselves in the market",
      "target_segment": "primary customer segment they target",
      "insight": "2 sentences on their product strategy and differentiation",
      "signal": "bullish or bearish or neutral or watch",
      "url": "their website url"
    }}
  ],
  "patterns": ["cross-competitor pattern 1", "pattern 2"],
  "takeaway": "Overall product and positioning takeaway for PH fintech market"
}}"""
    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def analyze_app_store(raw_apps: list[dict]) -> dict:
    competitors = _competitors_str(raw_apps)
    prompt = f"""You are a fintech product analyst specializing in the Philippines market.

Analyze the mobile app performance, user sentiment, and ratings of these Philippine fintech apps: {competitors}.

Based on your knowledge of their app store presence and user reviews, provide analysis.

Return ONLY raw JSON with no markdown or explanation:
{{
  "findings": [
    {{
      "competitor": "company name",
      "rating": 4.2,
      "rating_signal": "bullish or bearish or neutral or watch",
      "top_complaints": ["common user complaint 1", "complaint 2"],
      "top_praises": ["what users love 1", "praise 2"],
      "recent_update": "recent notable feature or change",
      "insight": "2 sentences on app quality and user sentiment",
      "signal": "bullish or bearish or neutral or watch"
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
    competitors = _competitors_str(raw_news)
    prompt = f"""You are a fintech industry analyst specializing in the Philippines market.

Summarize recent notable news, developments, and media coverage for these Philippine fintech companies: {competitors}.

Include partnerships, regulatory news, funding rounds, product launches, and media sentiment.

Return ONLY raw JSON with no markdown or explanation:
{{
  "findings": [
    {{
      "competitor": "company name",
      "headline": "notable recent development or news headline",
      "summary": "2 sentences explaining what happened and why it matters",
      "sentiment": "positive or negative or neutral",
      "signal": "bullish or bearish or neutral or watch",
      "url": null,
      "date": "approximate date or period"
    }}
  ],
  "patterns": ["industry trend 1", "trend 2"],
  "takeaway": "Overall news sentiment and industry direction for PH fintech"
}}"""
    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"findings": [], "takeaway": f"Analysis error: {e}"}


def generate_recommendations(all_sections: dict, competitors: list[str]) -> dict:
    comp_str = ", ".join(competitors)
    meta_takeaway = all_sections.get("meta_ads", {}).get("takeaway", "")
    web_takeaway = all_sections.get("websites", {}).get("takeaway", "")
    app_takeaway = all_sections.get("app_store", {}).get("takeaway", "")
    news_takeaway = all_sections.get("news", {}).get("takeaway", "")

    prompt = f"""You are a senior fintech strategy consultant for the Philippines market.

Based on this competitive intelligence summary for {comp_str}:

Meta Ads: {meta_takeaway}
Products & Websites: {web_takeaway}
App Store: {app_takeaway}
News & Media: {news_takeaway}

Provide strategic recommendations and competitive analysis.

Return ONLY raw JSON with no markdown or explanation:
{{
  "competitive_landscape": "2-3 sentences on the overall competitive situation in PH fintech",
  "biggest_threats": [
    {{
      "competitor": "company name",
      "threat": "what specifically makes them dangerous",
      "level": "high or medium or low"
    }}
  ],
  "opportunities": [
    {{
      "opportunity": "specific market gap or opening",
      "rationale": "why this is an opportunity right now"
    }}
  ],
  "recommendations": [
    {{
      "action": "specific concrete action to take",
      "priority": "high or medium or low",
      "rationale": "why this action matters"
    }}
  ],
  "watch_list": ["thing to monitor closely 1", "thing 2", "thing 3"]
}}"""
    try:
        return _ask_claude(prompt)
    except Exception as e:
        return {"competitive_landscape": f"Analysis error: {e}", "recommendations": []}
