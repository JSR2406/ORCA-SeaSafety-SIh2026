# Knowledge document metadata extraction.
#
# Only values that are found in real text/metadata are set - nothing is
# guessed.  Provided metadata always wins over text-derived inference.
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import List, Optional

_MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
           "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}

_AUTHORITY_KEYWORDS = [
    "ministry of", "coast guard", "fisheries department", "fisheries",
    "port authority", "marine", "harbour", "harbor", "icg", "daman",
    "advisory board", "secretariat", "environment department",
]

_DOC_TYPE_KEYWORDS = [
    ("regulation", "regulation"), ("gazette", "regulation"), ("act,", "regulation"),
    ("rules", "regulation"), ("by-laws", "regulation"),
    ("circular", "notice"), ("notification", "notice"), ("notice", "notice"),
    ("order", "notice"), ("bulletin", "notice"), ("press release", "notice"),
    ("advisory", "advisory"), ("warning", "advisory"), ("alert", "advisory"),
    ("guideline", "guideline"), ("guidelines", "guideline"), ("manual", "guideline"),
    ("handbook", "guideline"), ("operational", "guideline"),
    ("research paper", "research"), ("paper", "research"), ("journal", "research"),
    ("study", "research"), ("report", "report"),
]

_ISO_DATE_RE = re.compile(r"\b(1[6-9]\d{2}|20\d{2})-(0[1-9]|1[0-2])-(\d{2})\b")
_TEXT_DATE_RE = re.compile(
    r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    r"\s+((?:1[6-9]\d{2})|(?:20\d{2}))", re.IGNORECASE)
_EFFECTIVE_RE = re.compile(
    r"(?:effective\s+(?:from|date)|comes\s+into\s+effect\s+on)"
    r"[^0-9]{0,24}(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})", re.I)
_EXPIRY_RE = re.compile(
    r"(?:expires?\s+on|valid\s+(?:until|till|upto|up\s+to)\s+"
    r"(?:date\s+)?|shall\s+remain\s+in\s+force\s+until)[^0-9]{0,24}"
    r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})", re.I)
_REFERENCE_RE = re.compile(
    r"(?:no\.|no:|number|ref\.[.:]?)\s*[.:]?\s*([A-Z0-9][A-Z0-9/\-._]{3,40})\b", re.I)
_VERSION_RE = re.compile(r"\b(?:version\s*|v\.?)(\d+(?:\.\d+)?)\b", re.I)


@dataclass
class DocumentMetadata:
    title: Optional[str] = None
    source_url: Optional[str] = None
    source_type: str = "document"
    tags: List[str] = field(default_factory=list)
    language: str = "en-IN"
    authority: Optional[str] = None
    document_type: str = "other"
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    source_reference: Optional[str] = None
    version: int = 1

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


def compute_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _parse_found_date(text: str) -> Optional[str]:
    match = _ISO_DATE_RE.search(text)
    if match:
        return match.group(0)
    match = _TEXT_DATE_RE.search(text)
    if match:
        month = _MONTHS[match.group(2).lower()].__str__()
        return f"{match.group(3)}-{int(month):02d}-{int(match.group(1)):02d}"
    match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", text)
    if match:
        day, month, year = match.groups()
        year = int(year) + (2000 if int(year) < 100 else 0)
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return None


def _detect_language(text: str) -> str:
    if any('\u0d00' <= c <= '\u0d7f' for c in text):
        return "ml-IN"
    if any('\u0900' <= c <= '\u097f' for c in text):
        return "hi-IN"
    if any('\u0b80' <= c <= '\u0bff' for c in text):
        return "ta-IN"
    if any('\u0600' <= c <= '\u06ff' for c in text):
        return "ur-IN"
    return "en-IN"


def _classify_document_type(text: str) -> str:
    lowered = text.lower()
    for keyword, doc_type in _DOC_TYPE_KEYWORDS:
        if keyword in lowered:
            return doc_type
    return "other"


def _date_iso(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parsed = _parse_found_date(value)
    if parsed:
        return parsed
    try:
        if isinstance(value, datetime):
            return value.isoformat()
        return datetime.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        return None


def extract_document_metadata(
    text: str,
    filename: Optional[str] = None,
    provided: Optional[dict] = None,
) -> DocumentMetadata:
    provided = provided or {}
    first_lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:6]
    head = "\n".join(first_lines)

    title = None
    if provided.get("title"):
        title = str(provided["title"])
    else:
        for candidate in first_lines:
            stripped = candidate.strip()
            if stripped.endswith((".", "!", "?")) or len(stripped) > 120:
                continue
            if re.match(r"(?:no\.|no:|number|ref\.?)[\s:.]*[0-9]", stripped, re.I):
                continue
            if re.fullmatch(r"[\d\s/()\[\]:.\-]{2,}", stripped):
                continue
            if len(stripped.split()) < 2:
                continue
            if any(keyword in stripped.lower() for keyword in _AUTHORITY_KEYWORDS):
                continue
            title = stripped
            break

    authority = None
    if provided.get("authority"):
        authority = str(provided["authority"])
    else:
        for line in first_lines:
            lowered = line.lower()
            if any(k in lowered for k in _AUTHORITY_KEYWORDS):
                authority = line
                break

    document_type = provided.get("document_type") or _classify_document_type(title or head)
    language = provided.get("language") or _detect_language(head)

    publication_date = None
    if provided.get("publication_date"):
        publication_date = _date_iso(str(provided["publication_date"]))
    else:
        found = (_ISO_DATE_RE.search(head) or _TEXT_DATE_RE.search(head))
        if found:
            publication_date = _parse_found_date(found.group(0))

    effective_date = None
    if provided.get("effective_date"):
        effective_date = _date_iso(str(provided["effective_date"]))
    else:
        match = _EFFECTIVE_RE.search(text)
        if match:
            effective_date = _parse_found_date(match.group(1))

    expiry_date = None
    if provided.get("expiry_date"):
        expiry_date = _date_iso(str(provided["expiry_date"]))
    else:
        match = _EXPIRY_RE.search(text)
        if match:
            expiry_date = _parse_found_date(match.group(1))

    source_reference = None
    if provided.get("source_reference"):
        source_reference = str(provided["source_reference"])
    else:
        match = _REFERENCE_RE.search(head)
        if match:
            source_reference = match.group(1).strip()

    version = 1
    if provided.get("version") is not None:
        try:
            version = int(provided["version"])
        except (TypeError, ValueError):
            version = 1
    else:
        match = _VERSION_RE.search(head)
        if match:
            try:
                version = int(float(match.group(1)))
            except ValueError:
                version = 1

    tags = [str(t) for t in provided.get("tags", []) or []]

    return DocumentMetadata(
        title=title,
        source_url=provided.get("source_url") or None,
        source_type=str(provided.get("source_type") or "document"),
        tags=tags,
        language=language,
        authority=authority,
        document_type=document_type,
        publication_date=publication_date,
        effective_date=effective_date,
        expiry_date=expiry_date,
        source_reference=source_reference,
        version=version,
    )


def is_expired(expiry_date: Optional[str], now: Optional[datetime] = None) -> bool:
    if not expiry_date:
        return False
    now = now or datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(expiry_date)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed < now
    except (ValueError, TypeError):
        return False


def publication_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        return None


def to_datetime(value: Optional[str]) -> Optional[datetime]:
    return publication_datetime(value)