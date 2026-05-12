import httpx
import asyncio
import os
from datetime import datetime, timedelta

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
APIFY_BASE = "https://api.apify.com/v2"


async def _run_actor(actor_id: str, run_input: dict, timeout: int = 120) -> list[dict]:
    """Run an Apify actor and return dataset items."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        # Start actor run
        resp = await client.post(
            f"{APIFY_BASE}/acts/{actor_id}/runs",
            params={"token": APIFY_TOKEN},
            json=run_input,
        )
        resp.raise_for_status()
        run = resp.json()["data"]
        run_id = run["id"]

        # Poll until finished
        for _ in range(timeout // 5):
            await asyncio.sleep(5)
            status_resp = await client.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": APIFY_TOKEN},
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify actor {actor_id} failed with status: {status}")

        # Fetch dataset
        dataset_id = status_resp.json()["data"]["defaultDatasetId"]
        items_resp = await client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": APIFY_TOKEN, "format": "json", "limit": 100},
        )
        return items_resp.json()


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
                    "maxResults": 20,
                },
                timeout=180,
            )
            for item in items:
                results.append({
                    "competitor": competitor,
                    "source": "meta_ads",
                    "ad_id": item.get("adArchiveID", ""),
                    "headline": item.get("snapshot", {}).get("title", ""),
                    "body": item.get("snapshot", {}).get("body", {}).get("text", ""),
                    "cta": item.get("snapshot", {}).get("cta_text", ""),
                    "image_url": item.get("snapshot", {}).get("images", [{}])[0].get("original_image_url") if item.get("snapshot", {}).get("images") else None,
                    "page_name": item.get("pageName", competitor),
                    "start_date": item.get("startDate", ""),
                    "status": item.get("adDeliveryStartTime", "active"),
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
    competitor_urls = []
    for comp in competitors:
        if comp in urls:
            competitor_urls.append({"competitor": comp, "url": urls[comp]})

    if not competitor_urls:
        return results

    try:
        items = await _run_actor(
            "apify/web-scraper",
            {
                "startUrls": [{"url": u["url"]} for u in competitor_urls],
                "pageFunction": """async function pageFunction(context) {
                    const { page, request } = context;
                    const title = await page.title();
                    const text = await page.evaluate(() => document.body.innerText);
                    return { url: request.url, title, text: text.slice(0, 5000) };
                }""",
                "maxPagesPerCrawl": 3,
                "maxConcurrency": 3,
            },
            timeout=180,
        )
        for item in items:
            # Match URL back to competitor
            competitor = next(
                (u["competitor"] for u in competitor_urls if u["url"] in item.get("url", "")),
                "Unknown"
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
    """Scrape App Store and Google Play reviews and ratings."""
    results = []
    for comp in competitors:
        if comp not in app_ids:
            continue
        ids = app_ids[comp]
        try:
            items = await _run_actor(
                "apify/google-play-scraper",
                {
                    "appIds": [ids.get("android", "")],
                    "language": "en",
                    "country": "ph",
                    "numberOfReviews": 20,
                },
                timeout=120,
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
                        {
                            "text": r.get("text", ""),
                            "score": r.get("score", 0),
                            "date": r.get("date", ""),
                        }
                        for r in (item.get("reviews") or [])[:5]
                    ],
                })
        except Exception as e:
            results.append({"competitor": comp, "source": "google_play", "error": str(e)})

    return results


async def scrape_news(competitors: list[str]) -> list[dict]:
    """Scrape Google News for competitor mentions in Philippines."""
    results = []
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    for comp in competitors:
        try:
            items = await _run_actor(
                "apify/google-search-scraper",
                {
                    "queries": f"{comp} Philippines fintech after:{week_ago}",
                    "maxPagesPerQuery": 1,
                    "resultsPerPage": 10,
                    "countryCode": "ph",
                    "languageCode": "en",
                },
                timeout=120,
            )
            for item in items:
                for result in item.get("organicResults", []):
                    results.append({
                        "competitor": comp,
                        "source": "news",
                        "headline": result.get("title", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("description", ""),
                        "date": result.get("date", ""),
                    })
        except Exception as e:
            results.append({"competitor": comp, "source": "news", "error": str(e)})

    return results


# Default competitor URLs and app IDs
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
    """Run all scrapers sequentially and return combined raw data."""
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
