from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader

from app.services.errors import ServiceError

ALLOWED_SUFFIXES = {".txt", ".md", ".json", ".yaml", ".yml", ".pdf"}
MIME_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".pdf": "application/pdf",
}
PARSER_VERSION = "1.0.0"
NORMALIZER_VERSION = "1.0.0"


def parse_document(filename: str, payload: bytes, *, max_bytes: int = 2 * 1024 * 1024) -> tuple[str, str, dict[str, Any]]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ServiceError("unsupported_file_type", "Use a .txt, .md, .json, .yaml, or text-based .pdf file.")
    if len(payload) > max_bytes:
        raise ServiceError("file_too_large", f"File exceeds the {max_bytes} byte upload limit.")
    if not payload:
        raise ServiceError("empty_document", "The uploaded document is empty.")
    try:
        if suffix == ".pdf":
            reader = PdfReader(io.BytesIO(payload), strict=True)
            pages = [(page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n") for page in reader.pages]
            text = "\n\n".join(pages).strip()
            if len(text) < 20:
                raise ServiceError("pdf_has_no_text", "This PDF has no usable text. OCR and scanned PDFs are not supported.")
            provenance = {
                "pages": len(pages),
                "locator": "page_and_normalized_line",
                "parser": "pypdf",
                "parser_version": PARSER_VERSION,
                "normalizer": "aletheia_text",
                "normalizer_version": NORMALIZER_VERSION,
            }
        else:
            text = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            provenance = {
                "locator": "normalized_line",
                "parser": "utf8_text",
                "parser_version": PARSER_VERSION,
                "normalizer": "aletheia_text",
                "normalizer_version": NORMALIZER_VERSION,
            }
            if suffix == ".json":
                json.loads(text)
            elif suffix in {".yaml", ".yml"}:
                yaml.safe_load(text)
    except UnicodeDecodeError as error:
        raise ServiceError("invalid_utf8", "Documents must be UTF-8 text.") from error
    except (json.JSONDecodeError, yaml.YAMLError) as error:
        raise ServiceError("invalid_structured_document", f"The file could not be parsed safely: {error}") from error
    return text, MIME_TYPES[suffix], provenance
