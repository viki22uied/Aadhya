"""Hindi translation via Google Translate's free public endpoint (the same
one the unofficial `googletrans` package uses) — no API key, no local model.
Swapped in for Bhashini per user request: no signup step needed, so this
just works without asking for a key.

ponytail: this is the free/unofficial endpoint, not the paid Google Cloud
Translation API — no SLA, no key, can rate-limit or change without notice.
If it becomes unreliable, the paid Cloud Translation API is the upgrade path
(needs a billed GCP project + API key).
"""
import requests

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


class TranslateUnavailable(Exception):
    pass


def translate_to_hindi(text: str) -> str:
    """Translates plain English text to Hindi. Raises TranslateUnavailable
    on any request failure — callers must handle it and say so honestly,
    never silently fall back to untranslated text without flagging it."""
    try:
        response = requests.get(
            TRANSLATE_URL,
            params={"client": "gtx", "sl": "en", "tl": "hi", "dt": "t", "q": text},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return "".join(segment[0] for segment in data[0])
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as e:
        raise TranslateUnavailable(str(e)) from e
