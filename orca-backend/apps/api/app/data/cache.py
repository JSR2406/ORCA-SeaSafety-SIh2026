# Cache Layer
# Handles Parquet caching for offline demo mode and performance

import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd
import pyarrow.parquet as pq
from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages Parquet caches for ARGO data and query results."""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or settings.cached_data_path)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir = self.cache_dir / "profiles"
        self.observations_dir = self.cache_dir / "observations"
        self.query_results_dir = self.cache_dir / "query_results"
        for d in [self.profiles_dir, self.observations_dir, self.query_results_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, **params) -> str:
        key_str = str(sorted(params.items()))
        return hashlib.md5(key_str.encode()).hexdigest()[:16]

    # --- Profile/Observation Caches ---

    def cache_profiles(self, df: pd.DataFrame, key: str) -> Path:
        path = self.profiles_dir / f"{key}.parquet"
        df.to_parquet(path, compression="snappy")
        logger.info(f"Cached {len(df)} profiles to {path}")
        return path

    def cache_observations(self, df: pd.DataFrame, key: str) -> Path:
        path = self.observations_dir / f"{key}.parquet"
        df.to_parquet(path, compression="snappy")
        logger.info(f"Cached {len(df)} observations to {path}")
        return path

    def load_profiles(self, key: str) -> Optional[pd.DataFrame]:
        path = self.profiles_dir / f"{key}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return None

    def load_observations(self, key: str) -> Optional[pd.DataFrame]:
        path = self.observations_dir / f"{key}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return None

    # --- Query Result Cache ---

    def cache_query_result(self, query_hash: str, result: Dict[str, Any]) -> Path:
        path = self.query_results_dir / f"{query_hash}.parquet"
        # Store as JSON in a single-row DataFrame for simplicity
        import json
        df = pd.DataFrame([{"result": json.dumps(result, default=str)}])
        df.to_parquet(path, compression="snappy")
        return path

    def load_query_result(self, query_hash: str) -> Optional[Dict[str, Any]]:
        path = self.query_results_dir / f"{query_hash}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            if not df.empty:
                import json
                return json.loads(df.iloc[0]["result"])
        return None

    # --- Dataset Manifest ---

    def save_manifest(self, manifest: Dict[str, Any]) -> Path:
        path = self.cache_dir / "demo_manifest.json"
        import json
        path.write_text(json.dumps(manifest, indent=2, default=str))
        return path

    def load_manifest(self) -> Optional[Dict[str, Any]]:
        path = self.cache_dir / "demo_manifest.json"
        if path.exists():
            import json
            return json.loads(path.read_text())
        return None

    # --- Cache Management ---

    def list_cached_datasets(self) -> List[Dict[str, Any]]:
        """List all cached profile datasets."""
        datasets = []
        for path in self.profiles_dir.glob("*.parquet"):
            try:
                pf = pq.ParquetFile(path)
                meta = pf.metadata
                datasets.append({
                    "key": path.stem,
                    "path": str(path),
                    "rows": meta.num_rows,
                    "size_mb": path.stat().st_size / (1024 * 1024),
                })
            except Exception as e:
                logger.warning(f"Could not read {path}: {e}")
        return datasets

    def clear_cache(self, pattern: str = "*") -> int:
        """Clear cache files matching pattern."""
        count = 0
        for path in self.cache_dir.rglob(f"{pattern}.parquet"):
            path.unlink()
            count += 1
        logger.info(f"Cleared {count} cache files")
        return count


# Global cache instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager