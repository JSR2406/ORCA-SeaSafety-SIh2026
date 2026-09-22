# Document parsing abstraction for the knowledge ingestion pipeline.
#
# Each parser returns a `ParsedDocument` with normalized-friendly structure:
# full text plus ordered sections that preserve heading and page context.
# Formats are implemented only where the repository actually needs them:
# pdf, html and plain text (markdown maps to the text parser).  Anything else
# raises `UnsupportedFormatError` - never a pretended implementation.
import re
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from typing import List, Optional


class UnsupportedFormatError(ValueError):
    pass


@dataclass
class ParsedSection:
    heading: Optional[str]
    text: str
    page: Optional[int] = None


@dataclass
class ParsedDocument:
    title: Optional[str]
    text: str
    sections: List[ParsedSection] = field(default_factory=list)
    pages: List[str] = field(default_factory=list)
    format: str = "text"
    limitations: List[str] = field(default_factory=list)


class DocumentParser(ABC):
    format: str = "text"

    def __init__(self, filename: Optional[str] = None,
                 mime_type: Optional[str] = None):
        self.filename = filename
        self.mime_type = mime_type

    @abstractmethod
    def parse_bytes(self, content: bytes) -> ParsedDocument:
        raise NotImplementedError


def _decode(content: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return content.decode("utf-8", errors="replace")


# ------------------------------------------------------------------- text
class TextParser(DocumentParser):
    """Plain text: pages split on form-feed; sections = page blocks."""

    format = "text"

    def parse_bytes(self, content: bytes) -> ParsedDocument:
        text = _decode(content)
        pages = [p for p in re.split(r"\f", text) if p.strip()]
        sections, page_texts = [], []
        title = None
        for index, page in enumerate(pages, start=1):
            lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
            if not lines:
                continue
            page_text = "\n".join(lines)
            page_texts.append(page_text)
            heading = None
            if len(lines) == 1 or (len(lines[0]) <= 120
                                   and not lines[0].rstrip().endswith((".", "!", "?"))):
                heading = lines[0]
                body = "\n".join(lines[1:])
            else:
                body = page_text
            if title is None and heading:
                title = heading
            sections.append(ParsedSection(heading=heading, text=body, page=index))
        full_text = "\n\n".join(page_texts)
        return ParsedDocument(title=title, text=full_text, sections=sections,
                              pages=page_texts, format="text")


# ------------------------------------------------------------------- html
class _HtmlCollector(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title: Optional[str] = None
        self.parts: List[tuple] = []  # (heading_level, heading_text, body_text)
        self._skip_depth = 0
        self._in_title = False
        self._heading_level: Optional[int] = None
        self._heading_buffer: List[str] = []
        self._body_buffer: List[str] = []
        self._heading_mode = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = True
            return
        if re.fullmatch(r"h[1-6]", tag or ""):
            self._flush_part()
            self._heading_level = int(tag[1])
            self._heading_mode = True
            return
        if tag in ("p", "div", "li", "tr", "br", "section", "article"):
            self._body_buffer.append("\n")

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        if self._skip_depth:
            return
        if tag == "title":
            self._in_title = False
            return
        if re.fullmatch(r"h[1-6]", tag or ""):
            self._heading_mode = False
            return
        if tag in ("p", "div", "li", "tr", "section", "article"):
            self._body_buffer.append("\n")

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = " ".join(unescape(data).split())
        if self._in_title:
            return
        if self._skip_depth:
            return
        if data.strip():
            if self._heading_mode:
                self._heading_buffer.append(data)
            else:
                self._body_buffer.append(data)

    def _flush_part(self):
        heading = " ".join(" ".join(self._heading_buffer).split())
        body = " ".join(self._body_buffer)
        body = " ".join(body.split())
        level = self._heading_level
        self._heading_buffer = []
        self._body_buffer = []
        self._heading_level = None
        if heading or body:
            self.parts.append((level, heading, body))


class HtmlParser2(DocumentParser):
    """HTML: strips markup/scripts, preserves headings as sections."""

    format = "html"

    def parse_bytes(self, content: bytes) -> ParsedDocument:
        collector = _HtmlCollector()
        collector.feed(_decode(content))
        collector._flush_part()
        sections: List[ParsedSection] = []
        current: Optional[ParsedSection] = None
        for level, heading, body in collector.parts:
            if level is not None:
                if current is not None and current.text:
                    sections.append(current)
                current = ParsedSection(
                    heading=heading or f"H{level}", text=body)
            else:
                if current is None:
                    current = ParsedSection(heading=None, text=body)
                else:
                    current.text = f"{current.text}\n{body}".strip()
        if current is not None:
            sections.append(current)
        full_text = "\n\n".join(s.text for s in sections if s.text)
        pages = [full_text] if full_text else []
        title = collector.title
        primary = next((s for s in sections if s.heading), None)
        if title is None and primary:
            title = primary.heading
        return ParsedDocument(title=title, text=full_text, sections=sections,
                              pages=pages, format="html")


# ------------------------------------------------------------------- pdf
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_TX_BLOCK_RE = re.compile(rb"BT\b(.*?)\bET", re.DOTALL)
_TXT_STR_RE = re.compile(rb"\((?:\\\\.|[^\\\\()])*\)")


def _decode_pdf_string(raw: bytes) -> str:
    inner = raw[1:-1]
    out: List[str] = []
    index = 0
    while index < len(inner):
        byte = inner[index:index + 1]
        if byte == b"\\" and index + 1 < len(inner):
            nxt = inner[index + 1:index + 2]
            mapping = {b"n": "\n", b"r": "\r", b"t": "\t", b"(": "(", b")": ")",
                       b"\\": "\\"}
            out.append(mapping.get(nxt, " "))
            index += 2
        else:
            out.append(byte.decode("latin-1", errors="replace"))
            index += 1
    return "".join(out)


def _extract_pdf_text(stream: bytes) -> str:
    """Pull text operators (Tj / TJ) out of one decompressed content stream."""
    lines: List[str] = []
    for block in _TX_BLOCK_RE.finditer(stream):
        body = block.group(1)
        strings = [""]
        for match in _TXT_STR_RE.finditer(body):
            strings.append(_decode_pdf_string(match.group(0)))
        chunk = " ".join(s for s in strings if s)
        if chunk:
            lines.append(chunk)
    return "\n".join(lines)


class PdfParser(DocumentParser):
    """PDF text extraction via pypdf, with a minimal FlateDecode fallback.

    pypdf handles the common real-world PDFs (font-encoded legal text,
    multi-page gazettes, filters other than plain FlateDecode).  Pages become
    sections so heading/page context survives into chunks.  When pypdf yields
    nothing (e.g. fully scanned image PDFs) the legacy content-stream extractor
    is tried; if that also fails the parser raises UnsupportedFormatError
    instead of pretending it read the file.
    """

    format = "pdf"

    def parse_bytes(self, content: bytes) -> ParsedDocument:
        text, page_texts = self._extract_via_pypdf(content)
        if not (text and text.strip()):
            text, page_texts = self._extract_via_content_streams(content)
        if not (text and text.strip()):
            raise UnsupportedFormatError(
                "PDF contains no extractable text (scanned image PDFs and "
                "image-only files are not supported)")

        sections = [
            ParsedSection(heading=None, text=page_text, page=index)
            for index, page_text in enumerate(page_texts, start=1)
            if page_text and page_text.strip()
        ]
        if not sections:
            sections = [ParsedSection(heading=None, text=text, page=None)]
        pages = [p for p in page_texts if p and p.strip()]
        return ParsedDocument(
            title=None, text=text, sections=sections, pages=pages,
            format="pdf",
            limitations=["text-extracted per page; no layout/table recovery"],
        )

    @staticmethod
    def _extract_via_pypdf(content: bytes) -> tuple:
        """Return (full_text, [page_texts]) using pypdf when available."""
        raw_streams = []
        try:
            from io import BytesIO

            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            page_texts = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:  # noqa: BLE001 - keep other pages readable
                    page_text = ""
                page_texts.append(page_text)
            raw_streams = page_texts
        except Exception:  # noqa: BLE001 - fall through to legacy extractor
            return "", []
        full = "\n\n".join(p for p in raw_streams)
        return full, list(raw_streams)

    @staticmethod
    def _extract_via_content_streams(content: bytes) -> tuple:
        """Legacy heuristic: decompress FlateDecode streams, pull Tj/TJ."""
        extracted: List[str] = []
        for match in _STREAM_RE.finditer(content):
            raw = match.group(1)
            for candidate in (raw, raw.lstrip()):
                try:
                    decompressed = zlib.decompress(candidate)
                    text = _extract_pdf_text(decompressed)
                    if text.strip():
                        extracted.append(text)
                        break
                except zlib.error:
                    continue
        text = "\n\n".join(extracted)
        page_count = len(re.findall(rb"/Type\s*/Page[^s]", content)) or 1
        if page_count == 1 and text.strip():
            return text, [text]
        split = re.split(r"\n{2,}", text)
        return text, split if len(split) > 1 else ([text] if text.strip() else [])


# ----------------------------------------------------------------- dispatch
_FORMAT_BY_MIME = {
    "text/plain": "text",
    "text/markdown": "text",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/pdf": "pdf",
}
_EXTENSION_FORMATS = {
    ".txt": "text", ".md": "text", ".markdown": "text",
    ".html": "html", ".htm": "html",
    ".pdf": "pdf",
}


def parser_for(filename: Optional[str] = None,
               mime_type: Optional[str] = None) -> DocumentParser:
    fmt = None
    unknown_mime = not mime_type or mime_type.lower() in {
        "application/octet-stream", "application/binary", "binary/octet-stream"}
    if mime_type and not unknown_mime:
        fmt = _FORMAT_BY_MIME.get(mime_type.lower())
    if not fmt and (unknown_mime or not mime_type) and filename:
        fmt = _EXTENSION_FORMATS.get(
            re.search(r"(\.[^.]+)$", filename).group(1).lower()
            if re.search(r"(\.[^.]+)$", filename) else "")
    if not fmt:
        raise UnsupportedFormatError(
            f"unsupported document format: filename={filename!r} "
            f"mime_type={mime_type!r}")
    if fmt == "text":
        return TextParser(filename, mime_type)
    if fmt == "html":
        return HtmlParser2(filename, mime_type)
    return PdfParser(filename, mime_type)