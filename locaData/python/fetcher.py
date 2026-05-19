import time
import requests
from typing import List, Dict, Optional, Set


class PlacesFetcher:
    def __init__(
        self,
        api_key: str,
        nearby_url: str,
        rate_limit_rps: int = 10,
        max_pages_per_cell: int = 3,
        page_delay_seconds: int = 2,
        max_retries: int = 3,
        retry_backoff_base: int = 2
    ):
        self.api_key = api_key
        self.nearby_url = nearby_url
        self.rate_limit_rps = rate_limit_rps
        self.rate_limit_interval = 1.0 / rate_limit_rps
        self.max_pages = max_pages_per_cell
        self.page_delay = page_delay_seconds
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base
        self._last_request_time = 0.0
        self._global_ids: Set[str] = set()
        self._stats = {"total_api_calls": 0, "total_places": 0, "retries": 0, "cells_done": 0}

    def _wait_rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_interval:
            time.sleep(self.rate_limit_interval - elapsed)

    def _request(self, params: dict) -> Optional[dict]:
        for attempt in range(1, self.max_retries + 1):
            self._wait_rate_limit()
            try:
                resp = requests.get(self.nearby_url, params=params, timeout=15)
                self._last_request_time = time.time()
                self._stats["total_api_calls"] += 1

                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (429, 500, 502, 503, 504):
                    wait = self.retry_backoff_base ** attempt
                    print(f"   ⚠ API {resp.status_code}. Reintento {attempt}/{self.max_retries} en {wait}s")
                    self._stats["retries"] += 1
                    time.sleep(wait)
                    continue
                else:
                    print(f"   ✗ API error {resp.status_code}: {resp.text[:200]}")
                    return None
            except requests.exceptions.Timeout:
                wait = self.retry_backoff_base ** attempt
                print(f"   ⚠ Timeout. Reintento {attempt}/{self.max_retries} en {wait}s")
                time.sleep(wait)
                continue
            except requests.exceptions.RequestException as e:
                print(f"   ✗ Error de red: {e}")
                return None
        return None

    def fetch_cell(self, lat: float, lon: float, radius: int = 1000) -> List[dict]:
        cell_results: List[dict] = []
        cell_api_calls = 0
        all_page_results: List[dict] = []

        params = {
            "location": f"{lat},{lon}",
            "radius": radius,
            "key": self.api_key
        }

        data = self._request(params)
        if data is None or data.get("status") != "OK":
            return []

        cell_api_calls += 1
        results = data.get("results", [])
        all_page_results.extend(results)

        page_count = 1
        while "next_page_token" in data and page_count < self.max_pages:
            time.sleep(self.page_delay)
            page_params = {
                "pagetoken": data["next_page_token"],
                "key": self.api_key
            }
            data = self._request(page_params)
            if data is None or data.get("status") != "OK":
                break
            cell_api_calls += 1
            page_count += 1
            all_page_results.extend(data.get("results", []))

        for place in all_page_results:
            pid = place.get("place_id")
            if pid and pid not in self._global_ids:
                self._global_ids.add(pid)
                cell_results.append(place)

        self._stats["total_places"] += len(cell_results)
        self._stats["cells_done"] += 1
        return cell_results

    @property
    def stats(self) -> dict:
        return dict(self._stats)

    @staticmethod
    def extract_categories(place: dict) -> List[str]:
        types = place.get("types", [])
        if isinstance(types, list):
            return [t for t in types if isinstance(t, str)]
        return []

    @staticmethod
    def place_to_row(place: dict, cell_id: Optional[int] = None) -> dict:
        geom = place.get("geometry", {}) or {}
        loc = geom.get("location", {}) or {}
        types_val = place.get("types", [])
        types_str = ", ".join(types_val) if isinstance(types_val, list) else str(types_val)

        return {
            "place_id": place.get("place_id"),
            "business_name": place.get("name"),
            "types": types_str,
            "rating": place.get("rating"),
            "user_ratings_total": place.get("user_ratings_total"),
            "price_level": place.get("price_level"),
            "vicinity": place.get("vicinity"),
            "latitud": loc.get("lat"),
            "longitud": loc.get("lng"),
            "business_status": place.get("business_status"),
            "raw_data": place,
            "cell_id": cell_id
        }
