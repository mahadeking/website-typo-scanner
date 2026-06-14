"""Interactive Streamlit dashboard for Website Typo Scanner."""

from __future__ import annotations

import ipaddress
import os
import socket
from collections import Counter
from urllib.parse import urlsplit

import streamlit as st
from openai import OpenAI

from typo_scanner import (
    ALLOWED_ISSUE_TYPES,
    MAX_PAGES,
    OPENAI_MODEL,
    REQUEST_TIMEOUT,
    analyze_text_with_ai,
    crawl_website,
    generate_csv_report,
    generate_html_report,
    get_demo_results,
    normalize_url,
)


st.set_page_config(
    page_title="Website Typo Scanner",
    layout="wide",
    initial_sidebar_state="expanded",
)


def get_secret(name: str) -> str:
    """Read a Streamlit secret first, then fall back to an environment variable."""
    try:
        return str(st.secrets.get(name, "")).strip()
    except FileNotFoundError:
        return os.getenv(name, "").strip()


def require_optional_password() -> None:
    """Protect the app when APP_PASSWORD is configured by the owner."""
    configured_password = get_secret("APP_PASSWORD")
    if not configured_password:
        return

    if st.session_state.get("authenticated"):
        return

    st.title("Website Typo Scanner")
    st.caption("Enter the access password to continue.")
    entered_password = st.text_input("Access password", type="password")
    if st.button("Open scanner", type="primary", width="stretch"):
        if entered_password == configured_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


def is_public_website_url(url: str) -> tuple[bool, str]:
    """Reject malformed URLs and addresses that resolve to private networks."""
    normalized = normalize_url(url)
    if not normalized:
        return False, "Enter a complete HTTP or HTTPS URL."

    parsed = urlsplit(normalized)
    hostname = parsed.hostname
    if not hostname:
        return False, "The URL does not contain a valid hostname."

    if hostname.lower() == "localhost":
        return False, "Localhost URLs cannot be scanned from the hosted app."

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(
                hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
            )
        }
    except socket.gaierror:
        return False, "The website hostname could not be resolved."

    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return False, "Private, local, or reserved network addresses are blocked."

    return True, normalized


def issue_breakdown(issues: list[dict[str, str]]) -> None:
    """Show a compact visual issue breakdown using native Streamlit widgets."""
    counts = Counter(issue["issue_type"] for issue in issues)
    columns = st.columns(4)
    for column, issue_type in zip(columns, sorted(ALLOWED_ISSUE_TYPES)):
        column.metric(issue_type, counts.get(issue_type, 0))


def result_table(issues: list[dict[str, str]]) -> None:
    """Render scan issues as a responsive table."""
    if not issues:
        st.success("No issues were found in the scanned copy.")
        return

    rows = [
        {
            "#": index,
            "Page URL": issue["page_url"],
            "Issue Type": issue["issue_type"],
            "Found Text": issue["typo_found"],
            "Context Sentence": issue["context_sentence"],
            "Suggested Fix": issue["suggested_fix"],
        }
        for index, issue in enumerate(issues, start=1)
    ]
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={
            "Page URL": st.column_config.LinkColumn("Page URL"),
            "#": st.column_config.NumberColumn("#", width="small"),
        },
    )


require_optional_password()

st.title("Website Typo Scanner")
st.caption(
    "Scan public website copy for spelling, grammar, repeated words, and "
    "brand-name inconsistencies."
)

with st.sidebar:
    st.header("Scan Settings")
    target_url = st.text_input(
        "Website URL",
        value="https://themodernmedicinegroup.com",
        placeholder="https://example.com",
    )
    page_limit = st.slider("Maximum pages", 1, MAX_PAGES, min(10, MAX_PAGES))
    demo_mode = st.checkbox(
        "Use demo mode",
        value=not bool(get_secret("OPENAI_API_KEY")),
        help="Demo mode uses sample findings and does not crawl or call OpenAI.",
    )
    scan_clicked = st.button(
        "Scan Website", type="primary", width="stretch"
    )

    st.divider()
    st.caption(f"AI model: {OPENAI_MODEL}")
    if not get_secret("APP_PASSWORD"):
        st.warning(
            "No APP_PASSWORD is configured. Add one before sharing this app publicly."
        )

if scan_clicked:
    valid_url, url_or_error = is_public_website_url(target_url)
    if not valid_url:
        st.error(url_or_error)
        st.stop()

    normalized_url = url_or_error
    api_key = get_secret("OPENAI_API_KEY")
    if not demo_mode and not api_key:
        st.error(
            "OPENAI_API_KEY is not configured. Enable demo mode or add the key "
            "to your local .env / Streamlit secrets."
        )
        st.stop()

    progress = st.progress(0, text="Preparing scan...")
    status = st.empty()

    if demo_mode:
        status.info("Creating a dashboard with sample findings...")
        issues = get_demo_results(normalized_url)
        pages_scanned = len({issue["page_url"] for issue in issues})
        progress.progress(100, text="Demo report ready")
    else:
        status.info("Crawling internal pages...")

        def update_crawl_progress(pages_found: int, current_url: str) -> None:
            percent = min(40, max(2, int(pages_found / page_limit * 40)))
            progress.progress(
                percent,
                text=f"Collected {pages_found} page(s): {current_url}",
            )

        pages = crawl_website(
            normalized_url,
            max_pages=page_limit,
            status_callback=update_crawl_progress,
        )
        pages_scanned = len(pages)
        issues: list[dict[str, str]] = []

        if not pages:
            progress.empty()
            status.empty()
            st.error(
                "No readable HTML pages were found. The site may block crawlers, "
                "require JavaScript, or be unavailable."
            )
            st.stop()

        client = OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT * 2)
        for index, page in enumerate(pages, start=1):
            progress_value = 40 + int(index / pages_scanned * 60)
            progress.progress(
                progress_value,
                text=f"Analyzing page {index} of {pages_scanned}",
            )
            issues.extend(analyze_text_with_ai(client, page["url"], page["text"]))

        progress.progress(100, text="Scan complete")

    html_report = generate_html_report(
        issues, normalized_url, pages_scanned, demo_mode=demo_mode
    )
    csv_report = generate_csv_report(issues)
    st.session_state.scan_result = {
        "url": normalized_url,
        "issues": issues,
        "pages_scanned": pages_scanned,
        "html": html_report,
        "csv": csv_report,
        "demo_mode": demo_mode,
    }
    status.success("Scan complete.")

if result := st.session_state.get("scan_result"):
    st.subheader("Scan Summary")
    summary_columns = st.columns(4)
    summary_columns[0].metric("Website", urlsplit(result["url"]).netloc)
    summary_columns[1].metric("Pages Scanned", result["pages_scanned"])
    summary_columns[2].metric("Issues Found", len(result["issues"]))
    summary_columns[3].metric(
        "Mode", "Demo" if result["demo_mode"] else "Live"
    )

    issue_breakdown(result["issues"])

    download_columns = st.columns([1, 1, 2])
    download_columns[0].download_button(
        "Download HTML Report",
        data=result["html"],
        file_name="typo_report.html",
        mime="text/html",
        width="stretch",
    )
    download_columns[1].download_button(
        "Download CSV Report",
        data=result["csv"].encode("utf-8-sig"),
        file_name="typo_report.csv",
        mime="text/csv",
        width="stretch",
    )

    st.subheader("Issues")
    result_table(result["issues"])

    with st.expander("Preview full dashboard report"):
        st.html(result["html"])
else:
    st.info(
        "Enter a public website URL, choose demo or live mode, and click "
        "**Scan Website**."
    )
