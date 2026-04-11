"""
SFX Catalog — indexes sound effect files at startup for LLM-driven playback.
Scans the SFX_ROOT directory tree (set via env var or defaults to ../sfx_library), parses filenames into
searchable tags and descriptions.
"""

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

import os
SFX_ROOT = Path(os.getenv("SFX_ROOT", os.path.join(os.path.dirname(__file__), "..", "sfx_library")))
EXTRACTED_ROOT = Path(os.path.join(os.path.dirname(__file__), "..", "assets", "audio_extracted"))
AUDIO_EXTS = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}


@dataclass
class SfxEntry:
    id: str
    filename: str
    path: str
    collection: str       # "RJ01501628" or "RJ276666"
    category: str         # directory name
    tags: list[str]
    is_binaural: bool
    description: str


def _make_id(path: str) -> str:
    return hashlib.sha256(path.encode()).hexdigest()[:12]


def _extract_tags(filename: str, category: str) -> list[str]:
    """Extract searchable tags from Japanese filename + category."""
    text = filename + " " + category
    # Remove extension
    text = re.sub(r'\.\w+$', '', text)
    # Split on common delimiters
    parts = re.split(r'[（）()・、。\s\-_]+', text)
    # Also split on particles
    expanded = []
    for p in parts:
        expanded.append(p)
        # Split long tokens further on の/を/で/に/が/は/と
        if len(p) > 4:
            sub = re.split(r'(?<=[のをでにがはと])', p)
            expanded.extend(s for s in sub if len(s) > 1)
    # Dedupe and filter
    seen = set()
    tags = []
    for t in expanded:
        t = t.strip()
        if t and len(t) > 1 and t not in seen:
            seen.add(t)
            tags.append(t)
    return tags


class SfxCatalog:
    def __init__(self):
        self.entries: dict[str, SfxEntry] = {}
        self.by_category: dict[str, list[SfxEntry]] = {}

    def build(self, root: Path = SFX_ROOT) -> None:
        """Walk directory tree, build catalog from all sources."""
        self.entries.clear()
        self.by_category.clear()

        # Scan primary SFX library
        self._scan_dir(root)
        # Scan extracted Koikatsu audio
        if EXTRACTED_ROOT.exists():
            self._scan_dir(EXTRACTED_ROOT)

        logger.info(f"SFX catalog built: {len(self.entries)} entries, {len(self.by_category)} categories")

    def _scan_dir(self, root: Path) -> None:
        """Scan a single directory tree and add entries."""
        if not root.exists():
            logger.warning(f"SFX dir not found: {root}")
            return

        for audio_file in root.rglob("*"):
            if audio_file.suffix.lower() not in AUDIO_EXTS:
                continue
            if not audio_file.is_file():
                continue

            rel = audio_file.relative_to(root)
            parts = rel.parts

            # Extract collection (RJ number)
            collection = parts[0] if parts else ""

            # Extract category (deepest directory)
            category = parts[-2] if len(parts) >= 2 else ""

            # Check binaural
            is_binaural = "バイノーラル" in str(rel)

            # Build entry
            entry_id = _make_id(str(rel))
            filename = audio_file.stem
            tags = _extract_tags(filename, category)
            # Clean description
            desc = re.sub(r'[0-9]+$', '', filename).strip()
            if not desc:
                desc = filename

            entry = SfxEntry(
                id=entry_id,
                filename=filename,
                path=str(audio_file),
                collection=collection,
                category=category,
                tags=tags,
                is_binaural=is_binaural,
                description=desc,
            )

            self.entries[entry_id] = entry
            self.by_category.setdefault(category, []).append(entry)

    def search_by_tag(self, tag: str, limit: int = 3) -> list[SfxEntry]:
        """Search by semantic tag from sfx_tags.py. Most accurate method."""
        from sfx_tags import TAG_PATTERNS
        patterns = TAG_PATTERNS.get(tag, [])
        if not patterns:
            return self.search(query=tag, limit=limit)

        scored = []
        for entry in self.entries.values():
            text = entry.filename + " " + entry.description + " " + entry.category
            score = 0
            for pat in patterns:
                if re.search(pat, text):
                    score += 20
            if score > 0:
                if entry.is_binaural:
                    score += 2
                scored.append((score, entry))
        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def search(self, query: str = "", category: str = "", tag: str = "", limit: int = 5) -> list[SfxEntry]:
        """Search catalog by semantic tag, query string, and/or category."""
        # Prefer semantic tag search if provided
        if tag:
            return self.search_by_tag(tag, limit)

        # Check if query matches a known tag name
        from sfx_tags import TAG_PATTERNS
        if query in TAG_PATTERNS:
            return self.search_by_tag(query, limit)

        candidates = []

        if category:
            for cat, entries in self.by_category.items():
                if category in cat or cat in category:
                    candidates.extend(entries)
        else:
            candidates = list(self.entries.values())

        if not query:
            return candidates[:limit]

        # Score by query match against tags and description
        scored = []
        query_parts = [q.strip() for q in re.split(r'[\s　、]+', query) if q.strip()]

        for entry in candidates:
            score = 0
            text = (entry.description + " " + " ".join(entry.tags) + " " + entry.category)
            for qp in query_parts:
                if qp in text:
                    score += 10
                for t in entry.tags:
                    if qp in t or t in qp:
                        score += 3
            if entry.is_binaural:
                score += 1
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: -x[0])
        return [e for _, e in scored[:limit]]

    def get_categories(self) -> dict[str, int]:
        """Return {category: count} summary."""
        return {cat: len(entries) for cat, entries in self.by_category.items()}

    def get_url(self, entry: SfxEntry) -> str:
        return f"/api/sfx/{entry.id}"


# Singleton
sfx_catalog = SfxCatalog()
