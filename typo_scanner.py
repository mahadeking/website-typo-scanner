"""
Website Typo Scanner

Quick start:
1. Open a terminal in this folder.
2. Run: python -m pip install -r requirements.txt
3. Copy .env.example to .env and add your OPENAI_API_KEY.
4. Set BASE_URL below to the website you want to scan.
5. Run: python typo_scanner.py

The script saves typo_report.html and typo_report.csv in this folder.
If OPENAI_API_KEY is missing, it creates a demo report with sample results.
"""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
from collections import Counter, deque
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI


# Load optional local settings before reading environment-backed constants.
load_dotenv()


# ---------------------------------------------------------------------------
# Scanner settings
# ---------------------------------------------------------------------------

BASE_URL = "https://themodernmedicinegroup.com"
MAX_PAGES = 25
MAX_CHARS_PER_PAGE = 8000
REQUEST_TIMEOUT = 15
MAX_CRAWL_DEPTH = 2
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")

OUTPUT_DIRECTORY = Path(__file__).resolve().parent
HTML_REPORT_PATH = OUTPUT_DIRECTORY / "typo_report.html"
CSV_REPORT_PATH = OUTPUT_DIRECTORY / "typo_report.csv"

SYSTEM_PROMPT = (
    'Analyze the following website text for obvious spelling mistakes, typos, '
    'grammar mistakes, awkward wording, repeated words, and brand/name '
    'inconsistencies. Ignore code, technical variables, proper names, industry '
    'slang, URLs, phone numbers, addresses, medical credentials, and intentional '
    'brand wording. Return the results in a raw JSON array containing objects '
    'with these exact keys: "page_url", "issue_type", "typo_found", '
    '"context_sentence", and "suggested_fix". If no issues are found, return an '
    "empty array []."
)

ALLOWED_ISSUE_TYPES = {
    "Spelling Error",
    "Grammar / Wording",
    "Repeated Words",
    "Brand / Name Inconsistency",
}

ISSUE_TYPE_ALIASES = {
    "spelling": "Spelling Error",
    "spelling error": "Spelling Error",
    "typo": "Spelling Error",
    "grammar": "Grammar / Wording",
    "grammar / wording": "Grammar / Wording",
    "grammar/wording": "Grammar / Wording",
    "awkward wording": "Grammar / Wording",
    "repeated word": "Repeated Words",
    "repeated words": "Repeated Words",
    "brand inconsistency": "Brand / Name Inconsistency",
    "name inconsistency": "Brand / Name Inconsistency",
    "brand / name inconsistency": "Brand / Name Inconsistency",
    "brand/name inconsistency": "Brand / Name Inconsistency",
}

ISSUE_OUTPUT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "page_url": {"type": "string"},
            "issue_type": {
                "type": "string",
                "enum": sorted(ALLOWED_ISSUE_TYPES),
            },
            "typo_found": {"type": "string"},
            "context_sentence": {"type": "string"},
            "suggested_fix": {"type": "string"},
        },
        "required": [
            "page_url",
            "issue_type",
            "typo_found",
            "context_sentence",
            "suggested_fix",
        ],
        "additionalProperties": False,
    },
}

IGNORED_TAGS = [
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "form",
    "button",
    "menu",
    "svg",
    "canvas",
    "template",
]

IGNORED_FILE_EXTENSIONS = {
    ".7z",
    ".avi",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".rss",
    ".svg",
    ".tar",
    ".txt",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


def normalize_url(url: str, base_url: str | None = None) -> str:
    """Return a stable HTTP(S) URL without fragments or tracking queries."""
    absolute_url = urljoin(base_url or url, url)
    parsed = urlsplit(absolute_url)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if scheme not in {"http", "https"} or not hostname:
        return ""

    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")

    return urlunsplit((scheme, netloc, path, "", ""))


def is_internal_link(url: str, base_url: str) -> bool:
    """Return True when a URL is crawlable and belongs to the base domain."""
    normalized = normalize_url(url, base_url)
    normalized_base = normalize_url(base_url)
    if not normalized or not normalized_base:
        return False

    parsed = urlsplit(normalized)
    base_parsed = urlsplit(normalized_base)
    parsed_host = parsed.netloc.removeprefix("www.")
    base_host = base_parsed.netloc.removeprefix("www.")
    if parsed_host != base_host:
        return False

    suffix = Path(parsed.path).suffix.lower()
    return suffix not in IGNORED_FILE_EXTENSIONS


def collect_internal_links(
    soup: BeautifulSoup, current_url: str, base_url: str
) -> list[str]:
    """Collect normalized, same-domain links from a parsed page."""
    links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        candidate = normalize_url(href, current_url)
        if candidate and is_internal_link(candidate, base_url):
            links.add(candidate)

    return sorted(links)


def clean_page_text(soup: BeautifulSoup) -> str:
    """Extract visible, readable text from the body of an HTML page."""
    body = soup.body
    if body is None:
        return ""

    for tag in body.find_all(IGNORED_TAGS):
        tag.decompose()

    hidden_selectors = [
        "[hidden]",
        '[aria-hidden="true"]',
        '[type="hidden"]',
        '[style*="display:none"]',
        '[style*="display: none"]',
        '[style*="visibility:hidden"]',
        '[style*="visibility: hidden"]',
    ]
    for selector in hidden_selectors:
        for tag in body.select(selector):
            tag.decompose()

    text = body.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_CHARS_PER_PAGE]


def crawl_website(
    base_url: str,
    max_pages: int = MAX_PAGES,
    max_depth: int = MAX_CRAWL_DEPTH,
    exclude_paths: list[str] | None = None,
    status_callback: Any | None = None,
) -> list[dict[str, str]]:
    """Crawl a limited number of internal pages using breadth-first search."""
    start_url = normalize_url(base_url)
    if not start_url:
        print("The BASE_URL is invalid. No pages were crawled.")
        return []

    start_parts = urlsplit(start_url)
    start_host = start_parts.netloc
    alternate_host = (
        start_host.removeprefix("www.")
        if start_host.startswith("www.")
        else f"www.{start_host}"
    )
    alternate_start_url = urlunsplit(
        (start_parts.scheme, alternate_host, start_parts.path, "", "")
    )

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    seed_urls = [start_url]
    if alternate_start_url != start_url:
        seed_urls.append(alternate_start_url)

    queue: deque[tuple[str, int]] = deque((url, 0) for url in seed_urls)
    queued = set(seed_urls)
    visited: set[str] = set()
    pages: list[dict[str, str]] = []
    excluded_fragments = [
        fragment.strip().lower()
        for fragment in (exclude_paths or [])
        if fragment.strip()
    ]

    while queue and len(pages) < max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        if any(fragment in urlsplit(url).path.lower() for fragment in excluded_fragments):
            continue
        visited.add(url)

        try:
            response = session.get(
                url, timeout=REQUEST_TIMEOUT, allow_redirects=True
            )
            response.raise_for_status()
        except requests.RequestException as error:
            print(f"  Skipped {url}: {error}")
            continue

        content_type = response.headers.get("Content-Type", "").lower()
        looks_like_html = "<html" in response.text[:1000].lower()
        if "text/html" not in content_type and not looks_like_html:
            continue

        final_url = normalize_url(response.url)
        if not final_url or not is_internal_link(final_url, start_url):
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        text = clean_page_text(soup)
        if text:
            pages.append({"url": final_url, "text": text})
            if status_callback:
                status_callback(len(pages), final_url)

        if depth >= max_depth:
            continue

        for link in collect_internal_links(soup, final_url, start_url):
            if any(
                fragment in urlsplit(link).path.lower()
                for fragment in excluded_fragments
            ):
                continue
            if link not in visited and link not in queued:
                queue.append((link, depth + 1))
                queued.add(link)

    return pages


def parse_ai_json(raw_response: str) -> list[dict[str, str]]:
    """Parse raw JSON or fenced JSON and discard malformed issue objects."""
    if not raw_response or not raw_response.strip():
        return []

    cleaned = raw_response.strip()
    fenced_match = re.search(
        r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.IGNORECASE | re.DOTALL
    )
    if fenced_match:
        cleaned = fenced_match.group(1).strip()

    parsed: Any = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(cleaned):
            if character != "[":
                continue
            try:
                parsed, _ = decoder.raw_decode(cleaned[index:])
                break
            except json.JSONDecodeError:
                continue

    if isinstance(parsed, dict):
        parsed = parsed.get("issues", [])
    if not isinstance(parsed, list):
        return []

    required_keys = {
        "page_url",
        "issue_type",
        "typo_found",
        "context_sentence",
        "suggested_fix",
    }
    valid_issues: list[dict[str, str]] = []

    for item in parsed:
        if not isinstance(item, dict) or not required_keys.issubset(item):
            continue

        issue = {key: str(item.get(key, "")).strip() for key in required_keys}
        normalized_type = re.sub(r"\s+", " ", issue["issue_type"]).strip().lower()
        issue["issue_type"] = ISSUE_TYPE_ALIASES.get(
            normalized_type, issue["issue_type"]
        )
        if issue["issue_type"] not in ALLOWED_ISSUE_TYPES:
            continue
        if not all(issue.values()):
            continue
        valid_issues.append(issue)

    return valid_issues


def find_repeated_word_issues(page_url: str, page_text: str) -> list[dict[str, str]]:
    """Detect obvious consecutive repeated words without using the API."""
    issues: list[dict[str, str]] = []
    pattern = re.compile(r"\b([A-Za-z][A-Za-z'-]{1,})\s+\1\b", re.IGNORECASE)
    obvious_repeated_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "our",
        "that",
        "the",
        "their",
        "this",
        "to",
        "we",
        "with",
        "you",
        "your",
    }

    for match in pattern.finditer(page_text):
        repeated_word = match.group(1)
        if repeated_word.lower() not in obvious_repeated_words:
            continue
        if repeated_word[:1].isupper():
            continue

        start = max(
            page_text.rfind(".", 0, match.start()),
            page_text.rfind("!", 0, match.start()),
            page_text.rfind("?", 0, match.start()),
        )
        end_candidates = [
            position
            for punctuation in ".!?"
            if (position := page_text.find(punctuation, match.end())) != -1
        ]
        end = min(end_candidates) + 1 if end_candidates else min(
            len(page_text), match.end() + 120
        )
        context = page_text[start + 1 : end].strip()
        repeated = match.group(0)
        issues.append(
            {
                "page_url": page_url,
                "issue_type": "Repeated Words",
                "typo_found": repeated,
                "context_sentence": context or repeated,
                "suggested_fix": repeated_word,
            }
        )

    return issues[:10]


def analyze_text_with_ai(
    client: OpenAI,
    page_url: str,
    page_text: str,
    model: str = OPENAI_MODEL,
    error_callback: Any | None = None,
) -> list[dict[str, str]]:
    """Ask OpenAI to analyze one page and return validated issue objects."""
    user_input = f"Page URL: {page_url}\n\nWebsite text:\n{page_text}"

    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "low"},
            instructions=SYSTEM_PROMPT,
            input=user_input,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "website_copy_issues",
                    "schema": ISSUE_OUTPUT_SCHEMA,
                    "strict": True,
                }
            },
            max_output_tokens=4000,
        )
    except Exception as error:
        print(f"  AI analysis failed for {page_url}: {error}")
        if error_callback:
            error_callback(page_url, f"API request failed: {error}")
        return find_repeated_word_issues(page_url, page_text)

    issues = parse_ai_json(response.output_text)
    if not issues and response.output_text.strip() not in {"", "[]"}:
        message = "The AI response could not be parsed into valid findings."
        print(f"  {message} Page: {page_url}")
        if error_callback:
            error_callback(page_url, message)

    for issue in issues:
        # The crawler's URL is authoritative if the model changes or omits it.
        issue["page_url"] = page_url

    existing = {
        (
            issue["issue_type"].lower(),
            issue["typo_found"].lower(),
            issue["context_sentence"].lower(),
        )
        for issue in issues
    }
    for local_issue in find_repeated_word_issues(page_url, page_text):
        key = (
            local_issue["issue_type"].lower(),
            local_issue["typo_found"].lower(),
            local_issue["context_sentence"].lower(),
        )
        if key not in existing:
            issues.append(local_issue)

    return issues


def get_demo_results(base_url: str) -> list[dict[str, str]]:
    """Return mock data so the dashboard can be previewed without an API key."""
    root = normalize_url(base_url) or "https://example.com"
    return [
        {
            "page_url": f"{root}/about-us",
            "issue_type": "Spelling Error",
            "typo_found": "recieve",
            "context_sentence": "We recieve new patient requests every day.",
            "suggested_fix": "receive",
        },
        {
            "page_url": f"{root}/services",
            "issue_type": "Grammar / Wording",
            "typo_found": "Our team provide",
            "context_sentence": "Our team provide personalized care for every patient.",
            "suggested_fix": "Our team provides",
        },
        {
            "page_url": f"{root}/contact",
            "issue_type": "Repeated Words",
            "typo_found": "to to",
            "context_sentence": "Contact us today to to schedule your consultation.",
            "suggested_fix": "to",
        },
        {
            "page_url": f"{root}/our-team",
            "issue_type": "Brand / Name Inconsistency",
            "typo_found": "Modern Medical Group",
            "context_sentence": "Welcome to Modern Medical Group.",
            "suggested_fix": "The Modern Medicine Group",
        },
    ]


def highlight_typo(context: str, typo: str) -> str:
    """HTML-escape context and highlight every case-insensitive typo match."""
    if not typo:
        return html.escape(context)

    pattern = re.compile(re.escape(typo), flags=re.IGNORECASE)
    parts: list[str] = []
    last_index = 0

    for match in pattern.finditer(context):
        parts.append(html.escape(context[last_index : match.start()]))
        parts.append(
            f'<mark class="context-error">{html.escape(match.group(0))}</mark>'
        )
        last_index = match.end()

    parts.append(html.escape(context[last_index:]))
    return "".join(parts)


def generate_html_report(
    issues: list[dict[str, str]],
    base_url: str,
    pages_scanned: int,
    demo_mode: bool = False,
) -> str:
    """Generate the self-contained HTML dashboard report."""
    scan_time = datetime.now().astimezone().strftime("%B %d, %Y at %I:%M %p %Z")
    issue_counts = Counter(issue["issue_type"] for issue in issues)
    page_counts = Counter(issue["page_url"] for issue in issues)
    total_issues = len(issues)

    palette = {
        "Spelling Error": "#ef4444",
        "Grammar / Wording": "#f59e0b",
        "Repeated Words": "#8b5cf6",
        "Brand / Name Inconsistency": "#0ea5e9",
    }

    if total_issues:
        angle = 0.0
        gradient_parts = []
        for issue_type in ALLOWED_ISSUE_TYPES:
            count = issue_counts.get(issue_type, 0)
            if not count:
                continue
            next_angle = angle + (count / total_issues * 360)
            gradient_parts.append(
                f"{palette[issue_type]} {angle:.1f}deg {next_angle:.1f}deg"
            )
            angle = next_angle
        donut_gradient = ", ".join(gradient_parts)
    else:
        donut_gradient = "#dbe4f0 0deg 360deg"

    legend_html = "".join(
        (
            '<div class="legend-row">'
            f'<span class="legend-dot" style="background:{palette[issue_type]}">'
            "</span>"
            f"<span>{html.escape(issue_type)}</span>"
            f"<strong>{issue_counts.get(issue_type, 0)}</strong>"
            "</div>"
        )
        for issue_type in sorted(
            ALLOWED_ISSUE_TYPES,
            key=lambda name: issue_counts.get(name, 0),
            reverse=True,
        )
    )

    max_page_issues = max(page_counts.values(), default=1)
    page_bars_html = "".join(
        (
            '<div class="bar-row">'
            '<div class="bar-label">'
            f'<a href="{html.escape(url, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{html.escape(url)}</a>'
            f"<strong>{count}</strong>"
            "</div>"
            '<div class="bar-track">'
            f'<div class="bar-fill" style="width:{count / max_page_issues * 100:.1f}%">'
            "</div></div></div>"
        )
        for url, count in page_counts.most_common(8)
    )
    if not page_bars_html:
        page_bars_html = '<p class="empty-small">No issues to chart.</p>'

    top_types = issue_counts.most_common(3)
    top_total = sum(count for _, count in top_types)
    top_angle = 0.0
    top_gradient_parts = []
    for issue_type, count in top_types:
        next_angle = top_angle + (count / max(top_total, 1) * 360)
        top_gradient_parts.append(
            f"{palette[issue_type]} {top_angle:.1f}deg {next_angle:.1f}deg"
        )
        top_angle = next_angle
    top_gradient = (
        ", ".join(top_gradient_parts) if top_gradient_parts else "#dbe4f0 0deg 360deg"
    )
    top_legend_html = "".join(
        (
            '<div class="legend-row">'
            f'<span class="legend-dot" style="background:{palette[issue_type]}">'
            "</span>"
            f"<span>{html.escape(issue_type)}</span><strong>{count}</strong></div>"
        )
        for issue_type, count in top_types
    )
    if not top_legend_html:
        top_legend_html = '<p class="empty-small">No top issue types yet.</p>'

    rows_html = ""
    for index, issue in enumerate(issues, start=1):
        safe_url = html.escape(issue["page_url"], quote=True)
        issue_type_class = (
            "badge-" + re.sub(r"[^a-z]+", "-", issue["issue_type"].lower()).strip("-")
        )
        rows_html += f"""
        <tr>
          <td class="row-number">{index}</td>
          <td><a class="page-link" href="{safe_url}" target="_blank"
                 rel="noopener noreferrer">{html.escape(issue["page_url"])}</a></td>
          <td><span class="type-badge {issue_type_class}">{html.escape(issue["issue_type"])}</span></td>
          <td><span class="error-pill">{html.escape(issue["typo_found"])}</span></td>
          <td class="context-cell">{highlight_typo(issue["context_sentence"], issue["typo_found"])}</td>
          <td><span class="fix-pill">{html.escape(issue["suggested_fix"])}</span></td>
        </tr>"""

    if not rows_html:
        rows_html = """
        <tr>
          <td colspan="6" class="empty-state">
            No issues were found. The scanned copy looks clean.
          </td>
        </tr>"""

    demo_banner = ""
    if demo_mode:
        demo_banner = """
        <div class="demo-banner">
          Demo mode: OPENAI_API_KEY was not found, so this report uses sample data.
        </div>"""

    report = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Website Typo Report</title>
  <style>
    :root {{
      --navy: #13233f;
      --navy-soft: #23395d;
      --text: #334155;
      --muted: #64748b;
      --border: #e2e8f0;
      --surface: #ffffff;
      --background: #f4f7fb;
      --blue: #2563eb;
      --red: #dc2626;
      --red-bg: #fee2e2;
      --green: #15803d;
      --green-bg: #dcfce7;
      --shadow: 0 10px 30px rgba(15, 23, 42, 0.07);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--background);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
                   "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    .container {{ width: min(1480px, calc(100% - 40px)); margin: 0 auto; }}
    .topbar {{
      background: var(--navy);
      color: white;
      padding: 28px 0;
      box-shadow: 0 6px 20px rgba(15, 23, 42, 0.16);
    }}
    .topbar-inner {{ display: flex; justify-content: space-between; gap: 24px; align-items: center; }}
    h1 {{ margin: 0 0 4px; font-size: clamp(25px, 3vw, 36px); letter-spacing: -0.03em; }}
    .subtitle {{ margin: 0; color: #cbd5e1; }}
    .status-chip {{
      display: inline-flex; align-items: center; gap: 8px; padding: 8px 13px;
      border: 1px solid rgba(255,255,255,.18); border-radius: 999px;
      background: rgba(255,255,255,.08); font-size: 13px; font-weight: 700;
      white-space: nowrap;
    }}
    .status-dot {{ width: 8px; height: 8px; border-radius: 50%; background: #4ade80; }}
    main {{ padding: 30px 0 48px; }}
    .demo-banner {{
      margin-bottom: 20px; padding: 13px 16px; border: 1px solid #fde68a;
      border-radius: 12px; background: #fffbeb; color: #92400e; font-weight: 650;
    }}
    .summary-grid {{
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 18px; margin-bottom: 24px;
    }}
    .card {{
      background: var(--surface); border: 1px solid rgba(226,232,240,.8);
      border-radius: 18px; box-shadow: var(--shadow);
    }}
    .summary-card {{ padding: 22px; min-height: 132px; }}
    .eyebrow {{
      margin: 0 0 13px; color: var(--muted); font-size: 12px;
      font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
    }}
    .summary-value {{
      margin: 0; color: var(--navy); font-size: 28px; font-weight: 800;
      letter-spacing: -.03em;
    }}
    .summary-value.url {{
      font-size: 16px; line-height: 1.45; overflow-wrap: anywhere;
    }}
    .summary-note {{ margin: 7px 0 0; color: var(--muted); font-size: 13px; }}
    .completed {{ color: var(--green); }}
    .charts-grid {{
      display: grid; grid-template-columns: .9fr 1.4fr .9fr;
      gap: 18px; margin-bottom: 24px;
    }}
    .chart-card {{ padding: 22px; min-height: 310px; }}
    .card-title {{ margin: 0; color: var(--navy); font-size: 17px; }}
    .card-description {{ margin: 4px 0 22px; color: var(--muted); font-size: 13px; }}
    .donut-layout {{ display: flex; align-items: center; gap: 22px; }}
    .donut {{
      width: 140px; aspect-ratio: 1; border-radius: 50%; flex: 0 0 auto;
      position: relative;
    }}
    .donut::after {{
      content: ""; position: absolute; inset: 25%; border-radius: 50%;
      background: white; box-shadow: inset 0 0 0 1px var(--border);
    }}
    .legend {{ flex: 1; min-width: 0; }}
    .legend-row {{
      display: grid; grid-template-columns: 10px 1fr auto; align-items: center;
      gap: 8px; padding: 7px 0; font-size: 12px;
    }}
    .legend-dot {{ width: 9px; height: 9px; border-radius: 50%; }}
    .legend-row strong {{ color: var(--navy); }}
    .bar-row {{ margin-bottom: 16px; }}
    .bar-label {{
      display: flex; justify-content: space-between; gap: 12px;
      margin-bottom: 6px; font-size: 12px;
    }}
    .bar-label a {{
      color: var(--navy-soft); text-decoration: none; overflow: hidden;
      text-overflow: ellipsis; white-space: nowrap;
    }}
    .bar-track {{ height: 9px; border-radius: 999px; background: #e8eef7; overflow: hidden; }}
    .bar-fill {{
      height: 100%; min-width: 8px; border-radius: inherit;
      background: linear-gradient(90deg, #2563eb, #60a5fa);
    }}
    .empty-small {{ color: var(--muted); font-size: 13px; }}
    .table-card {{ overflow: hidden; }}
    .table-heading {{ padding: 22px 24px 17px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; min-width: 1120px; border-collapse: collapse; }}
    th {{
      padding: 14px 16px; background: var(--navy); color: white;
      font-size: 11px; letter-spacing: .055em; text-align: left; text-transform: uppercase;
    }}
    td {{
      padding: 16px; border-bottom: 1px solid var(--border);
      vertical-align: top; font-size: 13px;
    }}
    tbody tr:hover {{ background: #f8fafc; }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    .row-number {{ color: var(--muted); font-weight: 750; }}
    .page-link {{ color: var(--blue); font-weight: 650; text-decoration: none; overflow-wrap: anywhere; }}
    .page-link:hover {{ text-decoration: underline; }}
    .type-badge, .error-pill, .fix-pill {{
      display: inline-block; border-radius: 999px; padding: 5px 9px;
      font-size: 11px; font-weight: 750; line-height: 1.35;
    }}
    .type-badge {{ background: #eaf0f8; color: #3b506f; }}
    .badge-spelling-error {{ background: #fff1f2; color: #be123c; }}
    .badge-grammar-wording {{ background: #fffbeb; color: #b45309; }}
    .badge-repeated-words {{ background: #f5f3ff; color: #6d28d9; }}
    .badge-brand-name-inconsistency {{ background: #ecfeff; color: #0e7490; }}
    .error-pill {{ background: var(--red-bg); color: var(--red); }}
    .fix-pill {{ background: var(--green-bg); color: var(--green); }}
    .context-cell {{ min-width: 280px; max-width: 430px; }}
    .context-error {{
      padding: 1px 3px; border-radius: 4px; background: var(--red-bg);
      color: var(--red); font-weight: 750;
    }}
    .empty-state {{ padding: 54px; color: var(--muted); text-align: center; }}
    .footer {{ padding-top: 20px; color: var(--muted); font-size: 12px; text-align: center; }}
    @media (max-width: 1050px) {{
      .summary-grid {{ grid-template-columns: repeat(2, 1fr); }}
      .charts-grid {{ grid-template-columns: 1fr; }}
      .chart-card {{ min-height: 0; }}
    }}
    @media (max-width: 650px) {{
      .container {{ width: min(100% - 24px, 1480px); }}
      .topbar-inner {{ align-items: flex-start; flex-direction: column; }}
      .summary-grid {{ grid-template-columns: 1fr; }}
      .donut-layout {{ align-items: flex-start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <header class="topbar">
    <div class="container topbar-inner">
      <div>
        <h1>Website Typo Report</h1>
        <p class="subtitle">Scan completed on {html.escape(scan_time)}</p>
      </div>
      <div class="status-chip"><span class="status-dot"></span> Scan completed</div>
    </div>
  </header>

  <main class="container">
    {demo_banner}
    <section class="summary-grid" aria-label="Scan summary">
      <article class="card summary-card">
        <p class="eyebrow">Scanned Website</p>
        <p class="summary-value url">{html.escape(normalize_url(base_url) or base_url)}</p>
        <p class="summary-note">Internal pages only</p>
      </article>
      <article class="card summary-card">
        <p class="eyebrow">Pages Scanned</p>
        <p class="summary-value">{pages_scanned}</p>
        <p class="summary-note">Maximum configured: {MAX_PAGES}</p>
      </article>
      <article class="card summary-card">
        <p class="eyebrow">Total Issues Found</p>
        <p class="summary-value">{total_issues}</p>
        <p class="summary-note">Across all scanned pages</p>
      </article>
      <article class="card summary-card">
        <p class="eyebrow">Status</p>
        <p class="summary-value completed">Completed</p>
        <p class="summary-note">Reports are ready</p>
      </article>
    </section>

    <section class="charts-grid" aria-label="Issue overview">
      <article class="card chart-card">
        <h2 class="card-title">Overview</h2>
        <p class="card-description">Issue type breakdown</p>
        <div class="donut-layout">
          <div class="donut" style="background:conic-gradient({donut_gradient})"
               aria-label="{total_issues} total issues"></div>
          <div class="legend">{legend_html}</div>
        </div>
      </article>

      <article class="card chart-card">
        <h2 class="card-title">Issues by Page</h2>
        <p class="card-description">Pages with the most flagged copy</p>
        {page_bars_html}
      </article>

      <article class="card chart-card">
        <h2 class="card-title">Top Issue Types</h2>
        <p class="card-description">Leading categories in this scan</p>
        <div class="donut-layout">
          <div class="donut" style="background:conic-gradient({top_gradient})"
               aria-label="Top issue types"></div>
          <div class="legend">{top_legend_html}</div>
        </div>
      </article>
    </section>

    <section class="card table-card">
      <div class="table-heading">
        <h2 class="card-title">Detailed Results</h2>
        <p class="card-description">Review each finding before updating website copy.</p>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Page URL</th>
              <th>Issue Type</th>
              <th>Found Text</th>
              <th>Context Sentence</th>
              <th>Suggested Fix</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </section>
    <p class="footer">Generated locally by Website Typo Scanner</p>
  </main>
</body>
</html>
"""
    HTML_REPORT_PATH.write_text(report, encoding="utf-8")
    return report


def generate_csv_report(issues: list[dict[str, str]]) -> str:
    """Save issue data in a spreadsheet-friendly CSV file."""
    fieldnames = [
        "page_url",
        "issue_type",
        "typo_found",
        "context_sentence",
        "suggested_fix",
    ]
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(issues)
    csv_text = csv_buffer.getvalue()
    CSV_REPORT_PATH.write_text(csv_text, encoding="utf-8-sig", newline="")
    return csv_text


def main() -> None:
    """Run the crawler, AI analysis, and report generators."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    print("Website Typo Scanner")
    print(f"Target URL: {BASE_URL}")

    if not api_key:
        print("OPENAI_API_KEY was not found. Creating a demo report...")
        issues = get_demo_results(BASE_URL)
        pages_scanned = len({issue["page_url"] for issue in issues})
        generate_html_report(issues, BASE_URL, pages_scanned, demo_mode=True)
        generate_csv_report(issues)
    else:
        print("Crawling website and collecting pages...")
        pages = crawl_website(BASE_URL)
        pages_scanned = len(pages)
        print(f"Found {pages_scanned} internal pages.")

        client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT * 2)
        issues: list[dict[str, str]] = []
        for index, page in enumerate(pages, start=1):
            print(f"Scanning page {index} of {pages_scanned}...")
            issues.extend(analyze_text_with_ai(client, page["url"], page["text"]))

        generate_html_report(issues, BASE_URL, pages_scanned)
        generate_csv_report(issues)

    print("Scan complete.")
    print(f"Total pages scanned: {pages_scanned}")
    print(f"Total issues found: {len(issues)}")
    print(f"Report saved to: {HTML_REPORT_PATH.name}")
    print(f"CSV saved to: {CSV_REPORT_PATH.name}")


if __name__ == "__main__":
    main()
