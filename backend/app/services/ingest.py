"""Turns an uploaded file into plain text, and cleans pasted or extracted text."""
from __future__ import annotations

import io
import re

# Lines that are page furniture, not instructions: web chrome, feedback widgets, PDF footers.
BOILERPLATE = re.compile(
    r"^\s*(was this (article|page) helpful\??.*|yes\s*/?\s*no|share( this)?( article)?|print( this)?( article)?|"
    r"related articles?|(see|read) also|table of contents|contents|skip to (main )?content|cookie(s)? (settings|preferences|policy)|"
    r"we use cookies.*|accept( all)? cookies|page \d+( of \d+)?|\d+\s*/\s*\d+|copyright .*|\u00a9 .*|all rights reserved\.?|"
    r"(home|help center|support)\s*(>|\u203a|/).*|last updated:? .*|updated \d.*)\s*$",
    re.IGNORECASE,
)


def clean_article(text: str) -> str:
    """Removes page furniture and repairs PDF artefacts, keeping every instruction line.

    - joins words split across lines with a hyphen ("pass-\nword" -> "password")
    - turns bullet symbols into "- " so list items stay separate
    - drops boilerplate lines and collapses runs of blank lines and spaces
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"^[ \t]*[\u2022\u25cf\u25aa\u2023\u2043\u25e6][ \t]*", "- ", text, flags=re.MULTILINE)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    kept = [line for line in lines if not BOILERPLATE.match(line)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


class UnsupportedFile(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise UnsupportedFile("The file is not a valid PDF.")
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        if not data.startswith(b"PK"):
            raise UnsupportedFile("The file is not a valid DOCX.")
        from docx import Document

        document = Document(io.BytesIO(data))
        return "\n".join(p.text for p in document.paragraphs)
    raise UnsupportedFile("Use a .txt, .md, .pdf or .docx file.")
