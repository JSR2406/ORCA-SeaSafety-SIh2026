# Content normalization for knowledge ingestion.
#
# Keeps the structured view (sections, headings, pages) intact while cleaning
# whitespace, encoding and repeated per-page boilerplate.  It never rewrites or
# invents content - only removes noise.
import re
import unicodedata
from typing import List

from app.ingestion.document_parsers import ParsedDocument, ParsedSection

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE_RE = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    """Single-text normalization: encoding, whitespace, control chars."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_RE.sub("", text)
    lines = [_MULTI_SPACE_RE.sub(" ", ln).strip() for ln in text.split("\n")]
    return "\n".join(lines)


def drop_repeated_frame_lines(lines: List[str], threshold: float = 0.6,
                              frame: int = 2) -> List[str]:
    """Remove header/footer lines that recur at page edges (repeated copy)."""
    if not lines:
        return lines
    stripped = [ln.strip() for ln in lines]
    counts: dict = {}
    for line in stripped:
        if line:
            counts[line] = counts.get(line, 0) + 1
    edge_occurrences: dict = {}
    for i, line in enumerate(stripped):
        is_edge = i < frame or i >= len(stripped) - frame
        if line and is_edge:
            edge_occurrences[line] = edge_occurrences.get(line, 0) + 1
    drop_lines = {
        line for line in counts
        if counts[line] >= 3 and edge_occurrences.get(line, 0) >= frame
        and len(line) < 200
    }
    return [ln for ln in lines if ln.strip() not in drop_lines]


class DocumentNormalizer:
    """Normalizes a parsed document without destroying structure."""

    def normalize(self, document: ParsedDocument) -> ParsedDocument:
        sections = []
        for section in document.sections:
            text = section.text or ""
            page_lines = text.split("\n")
            page_lines = drop_repeated_frame_lines(page_lines)
            sections.append(ParsedSection(
                heading=section.heading,
                text=normalize_text("\n".join(page_lines)).strip(),
                page=section.page,
            ))
        sections = [s for s in sections if s.text]
        full_text = "\n\n".join(
            (f"{s.heading}\n" if s.heading else "") + s.text
            for s in sections)
        pages = [normalize_text(p) for p in document.pages if p.strip()]
        return ParsedDocument(
            title=document.title, text=full_text, sections=sections,
            pages=pages, format=document.format,
            limitations=list(document.limitations),
        )


def normalize_document(document: ParsedDocument) -> ParsedDocument:
    return DocumentNormalizer().normalize(document)