"""Text helpers: whole-word matching (D-012), HTML cleanup, and contact-data scrubbing."""
from __future__ import annotations

import html
import re
from functools import lru_cache

_INTERN_FORMS = re.compile(r"(?<!\w)intern(?:s|ships?)(?!\w)", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
_PROFILE_URL = re.compile(r"(?:https?://)?(?:[\w-]+\.)?linkedin\.com/\S*", re.I)
_CONTACT_SENTENCE = re.compile(r"\b(contact|reach out|recruiter|e-?mail|phone|call us|text us)\b", re.I)


def canon(text: str) -> str:
    """Lowercase, straighten quotes, collapse spaces, and fold 'interns'/'internship' to 'intern'.

    Folding lets the keyword 'tax intern' match the real title '2027 Summer Tax Internship'.
    """
    text = (text or "").replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", _INTERN_FORMS.sub("intern", text)).strip().lower()


@lru_cache(maxsize=None)
def _pattern(phrase: str):
    body = re.escape(canon(phrase)).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<!\w){body}(?!\w)")


def has_phrase(text: str, phrase: str) -> bool:
    """True only when the phrase appears as whole words: 'intern' never matches 'International'."""
    return bool(_pattern(phrase).search(canon(text)))


def html_to_text(raw: str) -> str:
    """Greenhouse escapes its HTML, so unescape before and after removing tags."""
    text = html.unescape(raw or "")
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"(?i)</(p|li|div|h\d)>|<br\s*/?>", ". ", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?:\s*\.\s*){2,}", ". ", text)


def sentences(text: str) -> list:
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text or "") if s.strip()]


def scrub_contact_data(text: str) -> str:
    """Remove emails, phone numbers, and profile links. The repo and site are public (D-004)."""
    text = _EMAIL.sub("[removed]", text or "")
    text = _PHONE.sub("[removed]", text)
    return _PROFILE_URL.sub("[removed]", text)


def make_snippet(description: str, limit: int = 280) -> str:
    """Short public summary. Sentences that invite contact are dropped, since they may name a person."""
    kept = [s for s in sentences(description) if not _CONTACT_SENTENCE.search(s)]
    snippet = scrub_contact_data(" ".join(kept))
    if len(snippet) <= limit:
        return snippet
    return snippet[:limit].rsplit(" ", 1)[0] + "..."


def normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", canon(title)).strip()
