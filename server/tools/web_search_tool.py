import logging
import httpx
from config import WebSearchConfig

logger = logging.getLogger(__name__)


class WebSearchTool:
    def __init__(self, config: WebSearchConfig):
        self.config = config
        self.searxng_url = config.base_url  # http://localhost:8080

    async def search(
        self,
        query: str,
        num_results: int = 10,
        language: str = "zh-TW",
    ) -> dict:
        # Try SearXNG first, fallback to Brave Search
        result = await self._search_searxng(query, num_results, language)
        if result.get("error"):
            logger.warning(f"SearXNG failed, trying Brave: {result['error']}")
            return await self._search_brave(query, num_results, language)
        return result

    async def _search_searxng(
        self, query: str, num_results: int, language: str
    ) -> dict:
        try:
            lang_map = {"zh-TW": "zh-TW", "ja": "ja", "en": "en"}
            lang = lang_map.get(language, "en")

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.searxng_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "language": lang,
                        "pageno": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            raw = data.get("results", [])[:num_results]
            results = []
            for item in raw:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("content", ""),
                    }
                )
            return {"results": results, "total": len(results), "query": query}
        except Exception as e:
            logger.error(f"SearXNG search failed: {e}")
            return {"error": str(e), "query": query}

    async def _search_brave(
        self, query: str, num_results: int, language: str
    ) -> dict:
        try:
            lang_map = {"zh-TW": "zh-tw", "ja": "ja-jp", "en": "en-us"}
            market = lang_map.get(language, "en-us")

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={
                        "q": query,
                        "count": num_results,
                        "search_lang": market,
                    },
                    headers={
                        "X-Subscription-Token": self.config.brave_api_key,
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            raw = data.get("web", {}).get("results", [])[:num_results]
            results = []
            for item in raw:
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", ""),
                    }
                )
            return {"results": results, "total": len(results), "query": query}
        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return {"error": str(e), "query": query}

    async def search_images(self, query: str, num_results: int = 5) -> dict:
        """Search for images using SearXNG."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.searxng_url}/search",
                    params={"q": query, "format": "json", "categories": "images", "pageno": 1},
                )
                resp.raise_for_status()
                data = resp.json()

            raw = data.get("results", [])[:num_results]
            media = []
            results = []
            for item in raw:
                img_url = item.get("img_src", "")
                title = item.get("title", "")
                source_url = item.get("url", "")
                if img_url:
                    media.append({"type": "image", "url": img_url, "alt": title})
                    results.append({"title": title, "image_url": img_url, "source_url": source_url})

            return {"results": results, "total": len(results), "query": query, "media": media}
        except Exception as e:
            logger.error(f"Image search failed: {e}")
            return {"error": str(e), "query": query}

    async def search_videos(self, query: str, num_results: int = 5) -> dict:
        """Search for videos using SearXNG."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.searxng_url}/search",
                    params={"q": query, "format": "json", "categories": "videos", "pageno": 1},
                )
                resp.raise_for_status()
                data = resp.json()

            raw = data.get("results", [])[:num_results]
            media = []
            results = []
            for item in raw:
                url = item.get("url", "")
                title = item.get("title", "")
                thumbnail = item.get("thumbnail", "") or item.get("img_src", "")
                iframe_src = item.get("iframe_src", "")
                if url:
                    results.append({"title": title, "url": url, "thumbnail": thumbnail, "iframe_src": iframe_src})
                    if iframe_src:
                        media.append({"type": "iframe", "url": iframe_src, "title": title, "thumbnail": thumbnail})
                    elif thumbnail:
                        media.append({"type": "image", "url": thumbnail, "alt": title})

            return {"results": results, "total": len(results), "query": query, "media": media}
        except Exception as e:
            logger.error(f"Video search failed: {e}")
            return {"error": str(e), "query": query}

    async def fetch_page_content(self, url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text(separator="\n", strip=True)
                return {"url": url, "content": text[:5000]}
        except Exception as e:
            logger.error(f"Fetch page failed: {e}")
            return {"error": str(e), "url": url}
