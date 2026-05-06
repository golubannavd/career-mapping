import json
import re
import anthropic

client = anthropic.Anthropic()

PROMPTS = {
    "news": lambda competitors: f"""Research the latest Philippines fintech news (past 4 weeks) about: {', '.join(competitors)}.
Return ONLY raw JSON (no markdown, no code fences, no explanation):
{{"findings":[{{"competitor":"string","headline":"string","detail":"2 sentences","signal":"bullish|bearish|neutral|watch","source":"string"}}],"takeaway":"string"}}""",

    "competitor": lambda competitors: f"""What new products, features, partnerships or campaigns have these companies launched recently in the Philippines: {', '.join(competitors)}?
Return ONLY raw JSON (no markdown, no code fences, no explanation):
{{"findings":[{{"competitor":"string","headline":"string","detail":"2 sentences","signal":"bullish|bearish|neutral|watch","source":"string"}}],"takeaway":"string"}}""",

    "social": lambda competitors: f"""Research recent social media activity of {', '.join(competitors)} on Instagram, Facebook, TikTok in the Philippines.
For each finding include a real post URL if found.
Return ONLY raw JSON (no markdown, no code fences, no explanation):
{{"platforms":{{"instagram":[{{"competitor":"string","headline":"string","observation":"string","signal":"bullish|bearish|neutral|watch","post_url":"string or null"}}],"facebook":[{{"competitor":"string","headline":"string","observation":"string","signal":"bullish|bearish|neutral|watch","post_url":"string or null"}}],"tiktok":[{{"competitor":"string","headline":"string","observation":"string","signal":"bullish|bearish|neutral|watch","post_url":"string or null"}}]}},"takeaway":"string"}}""",

    "press": lambda competitors: f"""Find recent press coverage of {', '.join(competitors)} in Philippine media (Inquirer, Rappler, BusinessWorld, CNN PH, etc).
Return ONLY raw JSON (no markdown, no code fences, no explanation):
{{"findings":[{{"competitor":"string","headline":"string","outlet":"string","sentiment":"positive|negative|neutral","detail":"2 sentences","signal":"bullish|bearish|neutral|watch","url":"string or null"}}],"takeaway":"string"}}""",

    "messaging": lambda competitors: f"""Analyze the product messaging, ads and marketing copy of {', '.join(competitors)} across all channels (social, OOH, TV, App Store) in the Philippines.
Return ONLY raw JSON (no markdown, no code fences, no explanation):
{{"items":[{{"competitor":"string","channel":"string","tagline":"exact copy or null","target_audience":"string","tone":"string","insight":"2 sentences"}}],"patterns":["string","string","string"],"takeaway":"string"}}""",

    "strategy": lambda competitors: f"""Based on public information, analyze the product and marketing strategy of {', '.join(competitors)} in Philippines fintech.
Return ONLY raw JSON (no markdown, no code fences, no explanation):
{{"profiles":[{{"competitor":"string","product_focus":"string","marketing_angle":"string","growth_lever":"string","weakness":"string","threat_level":"high|medium|low"}}],"patterns":["string","string","string"],"opportunities":["string","string"],"takeaway":"string"}}""",
}


def _extract_json(text: str) -> dict:
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Find outermost JSON object
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in response")
    return json.loads(match.group())


def research_section(section_id: str, competitors: list[str]) -> dict:
    prompt = PROMPTS[section_id](competitors)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=3000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Collect all text content blocks from the response
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    full_text = "\n".join(text_parts)

    if not full_text.strip():
        raise ValueError(f"No text content returned for section '{section_id}'")

    return _extract_json(full_text)
