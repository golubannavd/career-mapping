import httpx
import asyncio
import os
from datetime import datetime, timedelta

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
APIFY_BASE = "https://api.apify.com/v2"


async def _run_actor(actor_id: str, run_input: dict, timeout: int = 240) -> list[dict]:
    """Run an Apify actor and return dataset items."""
    async with httpx.AsyncClient(timeout=300) as client:
        # Start actor run
        resp = await client.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            params={"token": APIFY_TOKEN},
            json=run_input,
        )
        if resp.status_code != 201:
            raise RuntimeError(f"Failed to start actor {actor_id}: {resp.status_code} {resp.text[:300]}")

        run = resp.json()["data"]
        run_id = run["id"]

        # Poll until finished
        polls = timeout // 5
        status = "RUNNING"
        for _ in range(polls):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_TOKEN},
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Actor {actor_id} ended with status: {status}")

        if status != "SUCCEEDED":
            raise RuntimeError(f"Actor {actor_id} timed out (still {status} after {timeout}s)")

        dataset_id = status_resp.json()["data"]["defaultDatasetId"]
        items_resp = await client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN, "format": "json", "limit": 100},
        )
        items = items_resp.json()
        if not isinstance(items, list):
            raise RuntimeError(f"Unexpected dataset response: {str(items)[:200]}")
        return items


async def scrape_meta_ads(competitors: list[str]) -> list[dict]:
    """Scrape Meta Ads Library for competitor ads in the Philippines."""
    results = []
    for competitor in competitors:
        try:
            items = await _run_actor(
                "apify/facebook-ads-scraper",
                {
                    "searchTerms": [competitor],
                    "country": "PH",
                    "adType": "ALL",
                    "maxResults": 10,
                },
            )
            if not items:
                results.append({
                    "competitor": competitor,
                    "source": "meta_ads",
                    "error": "Actor ran successfully but returned 0 ads — the page may have no active ads in PH",
                })
                continue
            for item in items:
                snapshot = item.get("snapshot", {})
                images = snapshot.get("images", [])
                results.append({
                    "competitor": competitor,
                    "source": "meta_ads",
                    "ad_id": item.get("adArchiveID", ""),
                    "headline": snapshot.get("title", ""),
                    "body": (snapshot.get("body") or {}).get("text", "") if isinstance(snapshot.get("body"), dict) else str(snapshot.get("body", "")),
                    "cta": snapshot.get("cta_text", ""),
                    "image_url": images[0].get("original_image_url") if images else None,
                    "page_name": item.get("pageName", competitor),
                    "start_date": item.get("startDate", ""),
                    "platforms": item.get("publisherPlatform", []),
                    "url": f"https://www.facebook.com/ads/library/?id={item.get('adArchiveID', '')}",
                })
        except Exception as e:
            results.append({
                "competitor": competitor,
                "source": "meta_ads",
                "error": str(e),
            })
    return results


async def scrape_websites(competitors: list[str], urls: dict[str, str]) -> list[dict]:
    """Scrape competitor websites for product info, rates, offers."""
    results = []
    competitor_urls = [{"competitor": c, "url": urls[c]} for c in competitors if c in urls]
    if not competitor_urls:
        return results

    try:
        items = await _run_actor(
            "apify/cheerio-scraper",
            {
                "startUrls": [{"url": u["url"]} for u in competitor_urls],
                "maxCrawlPages": 2,
                "maxConcurrency": 3,
                "pageFunction": """async function pageFunction(context) {
                    const { $, request } = context;
                    const title = $('title').text().trim();
                    const text = $('body').text().replace(/\\s+/g, ' ').trim().slice(0, 4000);
                    return { url: request.url, title, text };
                }""",
            },
        )
        for item in items:
            competitor = next(
                (u["competitor"] for u in competitor_urls if u["url"] in item.get("url", "")),
                "Unknown",
            )
            results.append({
                "competitor": competitor,
                "source": "website",
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "text": item.get("text", ""),
            })
    except Exception as e:
        for u in competitor_urls:
            results.append({"competitor": u["competitor"], "source": "website", "error": str(e)})

    return results


async def scrape_app_store(competitors: list[str], app_ids: dict[str, dict]) -> list[dict]:
    """Scrape Google Play ratings and reviews."""
    results = []
    for comp in competitors:
        if comp not in app_ids:
            continue
        android_id = app_ids[comp].get("android", "")
        if not android_id:
            continue
        try:
            items = await _run_actor(
                "apify/google-play-scraper",
                {
                    "appIds": [android_id],
                    "language": "en",
                    "country": "ph",
                    "numberOfReviews": 10,
                },
            )
            for item in items:
                results.append({
                    "competitor": comp,
                    "source": "google_play",
                    "app_name": item.get("title", comp),
                    "rating": item.get("score", 0),
                    "reviews_count": item.get("ratings", 0),
                    "version": item.get("version", ""),
                    "updated": item.get("updated", ""),
                    "description": (item.get("description", "") or "")[:500],
                    "recent_reviews": [
                        {"text": r.get("text", ""), "score": r.get("score", 0), "date": r.get("date", "")}
                        for r in (item.get("reviews") or [])[:5]
                    ],
                })
        except Exception as e:
            results.append({"competitor": comp, "source": "google_play", "error": str(e)})

    return results


async def scrape_news(competitors: list[str]) -> list[dict]:
    """Scrape Google News for competitor mentions."""
    results = []
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    query = " OR ".join(competitors) + f" Philippines fintech after:{week_ago}"
    try:
        items = await _run_actor(
            "apify/google-search-scraper",
            {
                "queries": query,
                "maxPagesPerQuery": 1,
                "resultsPerPage": 20,
                "countryCode": "ph",
                "languageCode": "en",
            },
        )
        for item in items:
            for result in item.get("organicResults", []):
                title = result.get("title", "")
                snippet = result.get("description", "")
                url = result.get("url", "")
                # Match to competitor
                matched = next(
                    (c for c in competitors if c.lower() in title.lower() or c.lower() in snippet.lower()),
                    "General",
                )
                results.append({
                    "competitor": matched,
                    "source": "news",
                    "headline": title,
                    "url": url,
                    "snippet": snippet,
                    "date": result.get("date", ""),
                })
    except Exception as e:
        for c in competitors:
            results.append({"competitor": c, "source": "news", "error": str(e)})

    return results


COMPETITOR_URLS = {
    "GCash": "https://www.gcash.com",
    "Maya": "https://www.maya.ph",
    "HomeCredit": "https://www.homecredit.ph",
    "Salmon": "https://salmon.ph",
    "Maribank": "https://www.maribank.ph",
    "Billease": "https://billease.ph",
}

COMPETITOR_APP_IDS = {
    "GCash": {"android": "com.globe.gcash.android"},
    "Maya": {"android": "ph.maya.app"},
    "HomeCredit": {"android": "ph.com.homecredit.app"},
    "Salmon": {"android": "ph.salmon.app"},
    "Billease": {"android": "com.billease.app"},
}


async def run_all_scrapers(competitors: list[str], progress_cb=None) -> dict:
    raw = {}

    if progress_cb:
        await progress_cb("meta_ads", "loading")
    raw["meta_ads"] = await scrape_meta_ads(competitors)
    if progress_cb:
        await progress_cb("meta_ads", "done")

    if progress_cb:
        await progress_cb("websites", "loading")
    raw["websites"] = await scrape_websites(competitors, COMPETITOR_URLS)
    if progress_cb:
        await progress_cb("websites", "done")

    if progress_cb:
        await progress_cb("app_store", "loading")
    raw["app_store"] = await scrape_app_store(competitors, COMPETITOR_APP_IDS)
    if progress_cb:
        await progress_cb("app_store", "done")

    if progress_cb:
        await progress_cb("news", "loading")
    raw["news"] = await scrape_news(competitors)
    if progress_cb:
        await progress_cb("news", "done")

    return raw
