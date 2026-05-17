from __future__ import annotations

import html
import json
import math
import re
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


DEFAULT_SRD_URL = "https://www.dndbeyond.com/srd"
SRD_LICENSE = "Creative Commons Attribution 4.0 International"


@dataclass(frozen=True)
class RuleChunk:
    source_id: str
    title: str
    section: str
    text: str
    url: str
    license: str

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "section": self.section,
            "text": self.text,
            "url": self.url,
            "license": self.license,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuleChunk":
        required = ("source_id", "title", "section", "text", "url", "license")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Rule chunk missing required field(s): {', '.join(missing)}")
        return cls(
            source_id=str(data["source_id"]),
            title=str(data["title"]),
            section=str(data["section"]),
            text=str(data["text"]),
            url=str(data["url"]),
            license=str(data["license"]),
        )


@dataclass(frozen=True)
class RuleSearchResult:
    chunk: RuleChunk
    score: float

    def to_dict(self) -> dict:
        data = self.chunk.to_dict()
        data["score"] = round(self.score, 6)
        return data


class RuleCorpus:
    def __init__(self, chunks: Iterable[RuleChunk]) -> None:
        self.chunks = list(chunks)
        if not self.chunks:
            raise ValueError("Rule corpus must contain at least one chunk.")
        self._doc_tokens = [tokenize(chunk.title + " " + chunk.section + " " + chunk.text) for chunk in self.chunks]
        self._doc_lengths = [sum(tokens.values()) for tokens in self._doc_tokens]
        self._average_length = sum(self._doc_lengths) / len(self._doc_lengths)
        self._document_frequency: dict[str, int] = {}
        for tokens in self._doc_tokens:
            for token in tokens:
                self._document_frequency[token] = self._document_frequency.get(token, 0) + 1

    @classmethod
    def load_jsonl(cls, path: str | Path) -> "RuleCorpus":
        corpus_path = Path(path)
        if not corpus_path.exists():
            raise FileNotFoundError(f"Rule corpus not found: {corpus_path}")
        chunks: list[RuleChunk] = []
        for line_number, line in enumerate(corpus_path.read_text(encoding="utf-8-sig").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                chunks.append(RuleChunk.from_dict(json.loads(stripped)))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at line {line_number}: {exc.msg}") from exc
        return cls(chunks)

    def save_jsonl(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(chunk.to_dict(), ensure_ascii=False, sort_keys=True) for chunk in self.chunks]
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def search(self, query: str, limit: int = 5) -> list[RuleSearchResult]:
        if not query.strip():
            raise ValueError("Rules query cannot be empty.")
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored: list[RuleSearchResult] = []
        for index, tokens in enumerate(self._doc_tokens):
            score = self._bm25_score(query_tokens, tokens, self._doc_lengths[index])
            if score > 0:
                scored.append(RuleSearchResult(self.chunks[index], score))
        scored.sort(key=lambda result: (-result.score, result.chunk.title, result.chunk.section))
        return scored[:limit]

    def _bm25_score(self, query_tokens: dict[str, int], doc_tokens: dict[str, int], doc_length: int) -> float:
        score = 0.0
        k1 = 1.5
        b = 0.75
        for token, query_count in query_tokens.items():
            term_frequency = doc_tokens.get(token, 0)
            if term_frequency == 0:
                continue
            document_frequency = self._document_frequency.get(token, 0)
            inverse_document_frequency = math.log(
                1 + (len(self.chunks) - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = term_frequency + k1 * (1 - b + b * doc_length / self._average_length)
            score += query_count * inverse_document_frequency * (term_frequency * (k1 + 1) / denominator)
        return score


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "li", "tr", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "li", "tr", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return normalize_text("\n".join(self.parts))


def tokenize(text: str) -> dict[str, int]:
    tokens: dict[str, int] = {}
    for token in re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", text.lower()):
        tokens[token] = tokens.get(token, 0) + 1
    return tokens


def normalize_text(text: str) -> str:
    lines = []
    for line in html.unescape(text).splitlines():
        stripped = " ".join(line.split())
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def chunks_from_html(
    html_text: str,
    source_id: str = "srd-5.2.1",
    title: str = "DND SRD",
    url: str = DEFAULT_SRD_URL,
    license_name: str = SRD_LICENSE,
    max_chars: int = 1200,
) -> list[RuleChunk]:
    parser = _ReadableHTMLParser()
    parser.feed(html_text)
    return chunks_from_text(
        parser.text(),
        source_id=source_id,
        title=title,
        url=url,
        license_name=license_name,
        max_chars=max_chars,
    )


def chunks_from_text(
    text: str,
    source_id: str,
    title: str,
    url: str,
    license_name: str,
    max_chars: int = 1200,
) -> list[RuleChunk]:
    normalized = normalize_text(text)
    paragraphs = [paragraph.strip() for paragraph in normalized.splitlines() if paragraph.strip()]
    chunks: list[RuleChunk] = []
    current_section = title
    buffer: list[str] = []
    for paragraph in paragraphs:
        if _looks_like_heading(paragraph):
            _flush_chunk(chunks, buffer, source_id, title, current_section, url, license_name)
            current_section = paragraph
            buffer = []
            continue
        if sum(len(part) + 1 for part in buffer) + len(paragraph) > max_chars:
            _flush_chunk(chunks, buffer, source_id, title, current_section, url, license_name)
            buffer = []
        buffer.append(paragraph)
    _flush_chunk(chunks, buffer, source_id, title, current_section, url, license_name)
    return chunks


def build_srd_corpus(
    output_path: str | Path,
    source_url: str = DEFAULT_SRD_URL,
    fetcher=None,
) -> RuleCorpus:
    fetch = fetcher or _fetch_url
    html_text = fetch(source_url)
    chunks = chunks_from_html(html_text, source_id="srd-5.2.1", title="DND SRD 5.2.1", url=source_url)
    corpus = RuleCorpus(chunks)
    corpus.save_jsonl(output_path)
    return corpus


def format_search_results(results: list[RuleSearchResult]) -> str:
    if not results:
        return "No matching rules found."
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        chunk = result.chunk
        excerpt = chunk.text.replace("\n", " ")
        if len(excerpt) > 280:
            excerpt = excerpt[:277].rstrip() + "..."
        lines.extend(
            [
                f"{index}. {chunk.section} ({chunk.title})",
                f"   score: {result.score:.3f}",
                f"   source: {chunk.url}",
                f"   {excerpt}",
            ]
        )
    return "\n".join(lines)


def render_rules_context(results: list[RuleSearchResult], max_chars: int = 1800) -> str:
    if not results:
        return ""
    blocks: list[str] = []
    used = 0
    for result in results:
        chunk = result.chunk
        block = f"- {chunk.section} ({chunk.url}): {chunk.text}"
        if used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks)


def _flush_chunk(
    chunks: list[RuleChunk],
    buffer: list[str],
    source_id: str,
    title: str,
    section: str,
    url: str,
    license_name: str,
) -> None:
    text = "\n".join(buffer).strip()
    if not text:
        return
    chunks.append(
        RuleChunk(
            source_id=source_id,
            title=title,
            section=section,
            text=text,
            url=url,
            license=license_name,
        )
    )


def _looks_like_heading(paragraph: str) -> bool:
    if len(paragraph) > 90:
        return False
    words = paragraph.split()
    if not words:
        return False
    titleish = sum(1 for word in words if word[:1].isupper() or word.isupper())
    return titleish >= max(1, len(words) - 1) and not paragraph.endswith(".")


def _fetch_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "dnd-ai-assistant/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", errors="replace")
