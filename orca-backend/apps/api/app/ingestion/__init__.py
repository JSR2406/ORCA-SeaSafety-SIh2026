# Ingestion: fetch -> validate -> normalize -> dedup -> store -> track + scheduler.
from app.ingestion.dedup import dedup_batch, ensure_dedup_keys  # noqa: F401
from app.ingestion.mapping import map_records  # noqa: F401
from app.ingestion.pipeline import IngestionPipeline  # noqa: F401
from app.ingestion.scheduler import SourcePollingScheduler  # noqa: F401
from app.ingestion.validation import MarineValidationService  # noqa: F401