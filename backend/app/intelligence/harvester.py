"""
Encrypted Ledger - Macro Intelligence & Global News Harvester
Asynchronously crawls Jin10, Sina 7x24, and official exchange feeds for high-impact sentiment.
"""
from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.core.atomic_io import atomic_write_json, read_json_safe
from app.intelligence.circuit_breaker import circuit_breaker

NEWS_CACHE_FILE = settings.DATA_DIR / "news_sentiment.json"


class MacroNewsHarvester:
    """Institutional real-time global news aggregator and threat analyzer."""

    def __init__(self):
        self.cache_file = NEWS_CACHE_FILE

    async def fetch_jin10_news(self, limit: int = 25) -> List[Dict[str, Any]]:
        url = "https://cdn.jin10.com/json/index/hits_rank.json"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        items = []
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    raw = resp.json()
                    news_list = (raw.get("all", {}).get("daily", {}).get("news", [])
                                 + raw.get("all", {}).get("weekly", {}).get("news", []))
                    updated_at = raw.get("all", {}).get("daily", {}).get("updated_at")
                    now_ms = int(time.time() * 1000)
                    for idx, it in enumerate(news_list):
                        title = str(it.get("title") or "").strip()
                        if not title:
                            continue
                        nid = str(it.get("id") or f"jin10-{now_ms - idx*60000}")
                        items.append({
                            "id": f"jin10-{nid}",
                            "title": title,
                            "summary": f"金十数据热点要闻: {title}",
                            "source": "金十数据",
                            "time": updated_at or datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S"),
                            "timestamp_ms": now_ms - idx * 60000
                        })
        except Exception as e:
            logger.warning(f"Jin10 macro news fetch error: {e}")
        return items[:limit]

    async def fetch_sina_macro_feed(self, limit: int = 25) -> List[Dict[str, Any]]:
        url = "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=25&zhibo_id=152"
        headers = {"User-Agent": "Mozilla/5.0"}
        items = []
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    feed_list = data.get("result", {}).get("data", {}).get("feed", {}).get("list", [])
                    now_ms = int(time.time() * 1000)
                    for idx, it in enumerate(feed_list):
                        text = (it.get("rich_text") or it.get("plain_text") or "").strip()
                        if not text:
                            continue
                        create_time = it.get("create_time") or datetime.datetime.now(tz_bj).strftime("%Y-%m-%d %H:%M:%S")
                        title_match = re.split(r"[。！!？?\n]", text)[0].strip()
                        title = title_match[:75] if title_match else text[:75]
                        items.append({
                            "id": f"sina-{it.get('id') or (now_ms - idx*60000)}",
                            "title": title,
                            "summary": text[:250],
                            "source": "全球宏观快讯",
                            "time": create_time,
                            "timestamp_ms": now_ms - idx * 60000
                        })
        except Exception as e:
            logger.warning(f"Sina macro 7x24 news fetch error: {e}")
        return items[:limit]

    async def fetch_okx_announcements(self, limit: int = 15) -> List[Dict[str, Any]]:
        url = "https://www.okx.com/api/v5/support/announcements"
        headers = {"User-Agent": "Mozilla/5.0"}
        items = []
        tz_bj = datetime.timezone(datetime.timedelta(hours=8))
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    for group in data.get("data", []):
                        for it in (group.get("details", []) or []):
                            title = str(it.get("title") or "").strip()
                            if not title:
                                continue
                            p_time = int(it.get("pTime") or it.get("businessPTime") or (time.time() * 1000))
                            time_str = datetime.datetime.fromtimestamp(p_time / 1000.0, tz=tz_bj).strftime("%Y-%m-%d %H:%M:%S")
                            sha_tag = hashlib.sha256(title.encode("utf-8")).hexdigest()[:8]
                            items.append({
                                "id": f"okx-{p_time}-{sha_tag}",
                                "title": title,
                                "summary": f"OKX官方通告: {title}",
                                "source": "OKX官方公告",
                                "time": time_str,
                                "timestamp_ms": p_time
                            })
        except Exception as e:
            logger.warning(f"OKX announcement fetch error: {e}")
        return items[:limit]

    async def harvest_and_analyze(self) -> Dict[str, Any]:
        """Harvest all feeds concurrently, dedup, evaluate black swan regex, and persist."""
        results = await asyncio.gather(
            self.fetch_jin10_news(),
            self.fetch_sina_macro_feed(),
            self.fetch_okx_announcements(),
            return_exceptions=True
        )

        all_news: List[Dict[str, Any]] = []
        for r in results:
            if isinstance(r, list):
                all_news.extend(r)

        # Deduplicate
        seen_ids = set()
        deduped = []
        for n in all_news:
            nid = n.get("id")
            if nid and nid not in seen_ids:
                seen_ids.add(nid)
                deduped.append(n)

        # Sort by timestamp desc
        deduped.sort(key=lambda x: x.get("timestamp_ms", 0), reverse=True)

        # Run Black-Swan Sentinel Check on recent news (< 30 min)
        now_sec = time.time()
        for item in deduped:
            ts_sec = item.get("timestamp_ms", 0) / 1000.0
            if now_sec - ts_sec < 1800:
                circuit_breaker.check_headline(item.get("title", ""), item.get("summary", ""))

        payload = {
            "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "count": len(deduped),
            "news": deduped[:50]
        }
        atomic_write_json(self.cache_file, payload)
        return payload

    def get_latest_news_cache(self) -> Dict[str, Any]:
        return read_json_safe(self.cache_file, default={"news": [], "updated_at": ""})


news_harvester = MacroNewsHarvester()
