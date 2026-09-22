# Deterministic, configurable chunker for knowledge documents.
#
# Chunk boundaries are sentence-aware (regulatory statements are not split
# arbitrarily) and fully reproducible: the same document + same options yields
# identical chunk ids and chunk hashes.
import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.ingestion.document_normalization import normalize_text
from app.ingestion.document_parsers import ParsedDocument

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u0900-\u0d7f])")


@dataclass
class ChunkOptions:
    max_chars: int = 800
    overlap_chars: int = 64
    min_chars: int = 60


@dataclass
class Chunk:
    document_id: Optional[int]
    chunk_index: int
    content: str
    section: Optional[str]
    page: Optional[int]
    heading: Optional[str]
    metadata: dict = field(default_factory=dict)
    stable_id: str = ""
    chunk_hash: str = ""


def _split_into_atoms(section_text: str) -> List[str]:
    """Split normalized text into atomic sentence units (deterministic)."""
    atoms: List[str] = []
    for paragraph in re.split(r"\n{2,}", section_text):
        for sentence in re.split(r"\n", paragraph):
            sentence = sentence.strip()
            if not sentence:
                continue
            for part in _SENTENCE_RE.split(sentence):
                part = part.strip()
                if part:
                    atoms.append(part)
    return atoms


def _chunk_id(document_hash: str, index: int) -> str:
    return f"{document_hash[:12]}-{index}"


def _chunk_hash(document_hash: str, index: int, content: str,
                section: Optional[str], page: Optional[int]) -> str:
    payload = f"{document_hash}:{index}:{section}:{page}:{content}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def chunk_document(document_hash: str, document: ParsedDocument,
                   options: Optional[ChunkOptions] = None) -> List[Chunk]:
    """Chunk a normalized parsed document.

    Greedy accumulation on sentence atoms; a chunk never contains a partial
    sentence unless a single sentence exceeds max_chars (then it is hard-split
    on words).  Overlap carries the trailing sentences of the previous chunk.
    """
    options = options or ChunkOptions()
    chunks: List[Chunk] = []
    buffer: List[str] = []
    buffer_len = 0

    def flush(index: int, section: Optional[str], page: Optional[int],
              heading: Optional[str]) -> Optional[Chunk]:
        nonlocal buffer, buffer_len
        content = normalize_text(" ".join(buffer)).strip()
        if content:
            meta = {"section": section, "page": page, "heading": heading}
            chunk = Chunk(
                document_id=None,
                chunk_index=index,
                content=content,
                section=section,
                page=page,
                heading=heading,
                metadata={k: v for k, v in meta.items() if v is not None},
                stable_id=_chunk_id(document_hash, index),
                chunk_hash=_chunk_hash(document_hash, index, content,
                                       section, page),
            )
            chunks.append(chunk)
            # Overlap: seed the next window with trailing sentences.
            carry: List[str] = []
            carry_len = 0
            for atom in reversed(buffer):
                if carry_len + len(atom) + 1 > options.overlap_chars:
                    break
                carry.insert(0, atom)
                carry_len += len(atom) + 1
            buffer = carry
            buffer_len = carry_len
            return chunk
        buffer = []
        buffer_len = 0
        return None

    for section in document.sections:
        section_heading = section.heading
        atoms = _split_into_atoms(section.text)
        for atom in atoms:
            if len(atom) > options.max_chars:
                flush(len(chunks), section_heading, section.page, section_heading)
                for piece in _sentence_hard_split(atom, options.max_chars):
                    if buffer and buffer_len + len(piece) > options.max_chars:
                        flush(len(chunks), section_heading, section.page,
                              section_heading)
                    buffer.append(piece)
                    buffer_len += len(piece) + 1
                continue
            if buffer_len + len(atom) > options.max_chars and buffer:
                flush(len(chunks), section_heading, section.page, section_heading)
            buffer.append(atom)
            buffer_len += len(atom) + 1
        flush(len(chunks), section_heading, section.page, section_heading)

    generated = [c for c in chunks if len(c.content) >= options.min_chars]
    if not generated and chunks:
        generated = [chunks[-1]]
    return generated


def _sentence_hard_split(text: str, max_chars: int) -> List[str]:
    words = text.split()
    pieces: List[str] = []
    current: List[str] = []
    current_len = 0
    for word in words:
        if current and current_len + len(word) + 1 > max_chars:
            pieces.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word) + 1
    if current:
        pieces.append(" ".join(current))
    return pieces