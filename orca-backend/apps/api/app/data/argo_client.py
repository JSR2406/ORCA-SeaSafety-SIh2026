# ARGO Data Client
# Wraps argopy for production use with caching, QC, and error handling

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
import xarray as xr
from argopy import DataFetcher
from app.config import settings

logger = logging.getLogger(__name__)


class ArgoClient:
    """Production wrapper for argopy DataFetcher."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or settings.cached_data_path) / "argopy"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fetcher = DataFetcher(cache_dir=str(self.cache_dir))

    def _cache_key(self, **params) -> str:
        """Generate cache key from query parameters."""
        key_str = str(sorted(params.items()))
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    def _cached_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.parquet"

    async def fetch_region(
        self,
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float,
        min_depth: float = 0,
        max_depth: float = 2000,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        use_cache: bool = True,
    ) -> xr.Dataset:
        """
        Fetch ARGO profiles for a geographic region.
        
        Args:
            min_lon, max_lon: Longitude bounds
            min_lat, max_lat: Latitude bounds
            min_depth, max_depth: Depth bounds in meters
            start_date, end_date: ISO date strings (YYYY-MM-DD)
            use_cache: Whether to use cached data
        
        Returns:
            xarray Dataset with ARGO profiles
        """
        params = {
            "min_lon": min_lon, "max_lon": max_lon,
            "min_lat": min_lat, "max_lat": max_lat,
            "min_depth": min_depth, "max_depth": max_depth,
            "start_date": start_date, "end_date": end_date,
        }
        cache_key = self._cache_key(**params)
        cache_path = self._cached_path(cache_key)

        if use_cache and cache_path.exists():
            logger.info(f"Loading ARGO data from cache: {cache_path}")
            return pd.read_parquet(cache_path)

        # Run in thread pool since argopy is synchronous
        loop = asyncio.get_event_loop()
        dataset = await loop.run_in_executor(
            None,
            self._fetch_region_sync,
            min_lon, max_lon, min_lat, max_lat,
            min_depth, max_depth, start_date, end_date,
        )

        if use_cache and dataset is not None:
            logger.info(f"Caching ARGO data to: {cache_path}")
            dataset.to_dataframe().to_parquet(cache_path)

        return dataset

    def _fetch_region_sync(
        self,
        min_lon: float, max_lon: float,
        min_lat: float, max_lat: float,
        min_depth: float, max_depth: float,
        start_date: Optional[str], end_date: Optional[str],
    ) -> Optional[xr.Dataset]:
        """Synchronous fetch using argopy."""
        try:
            region = [min_lon, max_lon, min_lat, max_lat, min_depth, max_depth]
            if start_date and end_date:
                region.extend([start_date, end_date])

            ds = self.fetcher.region(region).to_xarray()
            logger.info(f"Fetched {ds.sizes.get('N_PROF', 0)} profiles from ARGO")
            return ds
        except Exception as e:
            logger.error(f"ARGO fetch failed: {e}")
            return None

    async def fetch_float(
        self,
        platform_number: int,
        cycle_numbers: Optional[List[int]] = None,
        use_cache: bool = True,
    ) -> Optional[xr.Dataset]:
        """Fetch profiles for a specific float."""
        params = {"platform_number": platform_number, "cycles": cycle_numbers}
        cache_key = self._cache_key(**params)
        cache_path = self._cached_path(cache_key)

        if use_cache and cache_path.exists():
            return pd.read_parquet(cache_path)

        loop = asyncio.get_event_loop()
        dataset = await loop.run_in_executor(
            None,
            lambda: self.fetcher.float(platform_number).to_xarray()
            if cycle_numbers is None
            else self.fetcher.float(platform_number).cycle(cycle_numbers).to_xarray(),
        )

        if use_cache and dataset is not None:
            dataset.to_dataframe().to_parquet(cache_path)

        return dataset

    async def fetch_profile(
        self,
        platform_number: int,
        cycle_number: int,
        use_cache: bool = True,
    ) -> Optional[xr.Dataset]:
        """Fetch a single profile."""
        params = {"platform_number": platform_number, "cycle_number": cycle_number}
        cache_key = self._cache_key(**params)
        cache_path = self._cached_path(cache_key)

        if use_cache and cache_path.exists():
            return pd.read_parquet(cache_path)

        loop = asyncio.get_event_loop()
        dataset = await loop.run_in_executor(
            None,
            lambda: self.fetcher.profile(platform_number, cycle_number).to_xarray(),
        )

        if use_cache and dataset is not None:
            dataset.to_dataframe().to_parquet(cache_path)

        return dataset


# Global client instance
_argo_client: Optional[ArgoClient] = None


def get_argo_client() -> ArgoClient:
    global _argo_client
    if _argo_client is None:
        _argo_client = ArgoClient()
    return _argo_client