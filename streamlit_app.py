"""Interactive Streamlit dashboard for Website Typo Scanner."""

from __future__ import annotations

import html
import ipaddress
import os
import re
import socket
from collections import Counter
from datetime import datetime
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


def inject_styles() -> None:
    """Apply the visual system for the Streamlit application."""
    st.html(
        """
        <style>
          :root {
            --ink: #0f1f3d;
            --muted: #63708a;
            --line: #e3e9f2;
            --blue: #2864ff;
            --blue-dark: #1747c7;
            --surface: #ffffff;
            --canvas: #f4f7fb;
            --green: #14804a;
            --red: #c93645;
          }

          .stApp {
            background:
              radial-gradient(circle at 84% 3%, rgba(40, 100, 255, .09), transparent 24rem),
              var(--canvas);
          }

          [data-testid="stHeader"] {
            background: transparent;
          }

          [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--line);
          }

          [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            gap: .85rem;
          }

          [data-testid="stMainBlockContainer"] {
            max-width: 1380px;
            padding-top: 2rem;
            padding-bottom: 4rem;
          }

          h1, h2, h3 {
            color: var(--ink);
            letter-spacing: -.025em;
          }

          .report-header {
            margin: 2px 0 24px;
            text-align: center;
          }

          .report-header h1 {
            margin: 0;
            color: var(--ink);
            font-size: clamp(31px, 4vw, 46px);
            line-height: 1.08;
            letter-spacing: -.05em;
          }

          .report-header p {
            margin: 8px 0 0;
            color: var(--muted);
            font-size: 13px;
          }

          .sidebar-brand {
            margin: -4px -6px 6px;
            padding: 18px;
            border-radius: 18px;
            background: linear-gradient(145deg, #0f2141, #173f8f);
            box-shadow: 0 14px 28px rgba(15, 33, 65, .18);
          }

          .sidebar-brand strong {
            display: block;
            color: white;
            font-size: 19px;
            letter-spacing: -.03em;
          }

          .sidebar-brand span {
            color: #c7d6f2;
            font-size: 12px;
          }

          .sidebar-section-label {
            margin: 12px 0 0;
            color: #7a879d;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: .11em;
            text-transform: uppercase;
          }

          .model-card {
            padding: 14px;
            border: 1px solid #dce5f3;
            border-radius: 14px;
            background: #f7f9fd;
          }

          .model-card span {
            display: block;
            color: #738097;
            font-size: 10px;
            font-weight: 800;
            letter-spacing: .1em;
            text-transform: uppercase;
          }

          .model-card strong {
            display: block;
            margin-top: 4px;
            color: var(--ink);
            font-size: 13px;
          }

          .metric-card {
            min-height: 112px;
            padding: 18px;
            border: 1px solid rgba(220, 228, 240, .9);
            border-radius: 14px;
            background: var(--surface);
            box-shadow: 0 10px 28px rgba(15, 31, 61, .055);
          }

          .metric-label {
            color: #748096;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: .095em;
            text-transform: uppercase;
          }

          .metric-value {
            margin-top: 9px;
            color: var(--ink);
            font-size: clamp(22px, 3vw, 30px);
            font-weight: 800;
            line-height: 1.1;
            letter-spacing: -.045em;
            overflow-wrap: anywhere;
          }

          .metric-value.is-domain {
            font-size: 19px;
            letter-spacing: -.025em;
          }

          .metric-note {
            margin-top: 6px;
            color: #8590a3;
            font-size: 12px;
          }

          .section-heading {
            margin: 26px 0 4px;
            color: var(--ink);
            font-size: 23px;
            font-weight: 800;
            letter-spacing: -.035em;
          }

          .dashboard-card {
            min-height: 310px;
            padding: 20px;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: white;
            box-shadow: 0 9px 24px rgba(15, 31, 61, .05);
          }

          .dashboard-card h3 {
            margin: 0 0 18px;
            font-size: 15px;
          }

          .donut-layout {
            display: flex;
            align-items: center;
            gap: 22px;
            min-height: 220px;
          }

          .donut {
            display: grid;
            width: 150px;
            height: 150px;
            flex: 0 0 auto;
            place-items: center;
            border-radius: 50%;
          }

          .donut-center {
            display: grid;
            width: 86px;
            height: 86px;
            place-items: center;
            border-radius: 50%;
            background: white;
            box-shadow: inset 0 0 0 1px var(--line);
            text-align: center;
          }

          .donut-center strong {
            display: block;
            color: var(--ink);
            font-size: 25px;
            line-height: 1;
          }

          .donut-center span {
            color: #7a879b;
            font-size: 10px;
          }

          .chart-legend {
            flex: 1;
            min-width: 0;
          }

          .legend-item {
            display: grid;
            grid-template-columns: 9px 1fr auto;
            gap: 8px;
            align-items: center;
            padding: 7px 0;
            color: #68758c;
            font-size: 11px;
          }

          .legend-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
          }

          .legend-item strong {
            color: var(--ink);
          }

          .bar-item {
            display: grid;
            grid-template-columns: minmax(70px, 110px) 1fr 20px;
            gap: 10px;
            align-items: center;
            margin: 11px 0;
            font-size: 11px;
          }

          .bar-label {
            overflow: hidden;
            color: #607089;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .bar-track {
            height: 9px;
            overflow: hidden;
            border-radius: 999px;
            background: #edf1f7;
          }

          .bar-fill {
            height: 100%;
            min-width: 6px;
            border-radius: inherit;
            background: linear-gradient(90deg, #ff4d57, #ff747b);
          }

          .bar-count {
            color: var(--ink);
            font-weight: 800;
            text-align: right;
          }

          .results-shell {
            overflow-x: auto;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: white;
            box-shadow: 0 10px 28px rgba(15, 31, 61, .05);
          }

          .results-table {
            width: 100%;
            min-width: 1050px;
            border-collapse: collapse;
          }

          .results-table th {
            padding: 13px 14px;
            background: #10213d;
            color: white;
            font-size: 10px;
            letter-spacing: .05em;
            text-align: left;
            text-transform: uppercase;
          }

          .results-table td {
            padding: 13px 14px;
            border-bottom: 1px solid #edf0f5;
            color: #536078;
            font-size: 11px;
            vertical-align: top;
          }

          .results-table tr:last-child td {
            border-bottom: 0;
          }

          .results-table a {
            color: #2464dc;
            font-weight: 650;
            text-decoration: none;
          }

          .error-pill, .fix-pill, .type-pill {
            display: inline-block;
            padding: 5px 9px;
            border-radius: 999px;
            font-size: 10px;
            font-weight: 800;
          }

          .error-pill {
            background: #fff0f1;
            color: #d63d48;
          }

          .fix-pill {
            background: #ecfaf1;
            color: #17884d;
          }

          .type-pill {
            background: #fff0f1;
            color: #d63d48;
          }

          .context-hit {
            color: #d63d48;
            font-weight: 800;
          }

          .empty-dashboard {
            padding: 48px 22px;
            border: 1px dashed #cfd8e7;
            border-radius: 18px;
            background: rgba(255, 255, 255, .68);
            text-align: center;
          }

          .empty-dashboard strong {
            display: block;
            color: var(--ink);
            font-size: 20px;
          }

          .empty-dashboard span {
            display: block;
            margin-top: 7px;
            color: var(--muted);
            font-size: 13px;
          }

          .section-copy {
            margin-bottom: 15px;
            color: var(--muted);
            font-size: 13px;
          }

          [data-testid="stMetric"] {
            min-height: 112px;
            padding: 18px;
            border: 1px solid var(--line);
            border-radius: 16px;
            background: white;
            box-shadow: 0 8px 24px rgba(15, 31, 61, .045);
          }

          [data-testid="stMetricLabel"] {
            color: #6e7a91;
            font-weight: 700;
          }

          [data-testid="stMetricValue"] {
            color: var(--ink);
            font-weight: 800;
          }

          .stButton > button[kind="primary"] {
            min-height: 46px;
            border: 0;
            border-radius: 12px;
            background: linear-gradient(135deg, var(--blue), var(--blue-dark));
            box-shadow: 0 9px 20px rgba(40, 100, 255, .24);
            font-weight: 800;
          }

          .stButton > button[kind="primary"]:hover {
            box-shadow: 0 12px 26px rgba(40, 100, 255, .32);
            transform: translateY(-1px);
          }

          .stDownloadButton > button {
            min-height: 44px;
            border-color: #cfdaeb;
            border-radius: 12px;
            color: var(--ink);
            font-weight: 750;
          }

          [data-baseweb="input"] > div,
          [data-baseweb="select"] > div {
            border-radius: 12px;
          }

          [data-testid="stDataFrame"] {
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 17px;
            background: white;
            box-shadow: 0 10px 28px rgba(15, 31, 61, .05);
          }

          [data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 8px;
            padding: 5px;
            border: 1px solid var(--line);
            border-radius: 13px;
            background: white;
          }

          [data-testid="stTabs"] [data-baseweb="tab"] {
            height: 40px;
            border-radius: 9px;
            padding: 0 18px;
            font-weight: 750;
          }

          [data-testid="stTabs"] [aria-selected="true"] {
            background: #eaf0ff;
            color: #1747c7;
          }

          [data-testid="stAlert"] {
            border-radius: 14px;
          }

          .login-shell {
            max-width: 520px;
            margin: 10vh auto 26px;
            padding: 34px;
            border: 1px solid var(--line);
            border-radius: 24px;
            background: white;
            box-shadow: 0 22px 56px rgba(15, 31, 61, .12);
            text-align: center;
          }

          .login-mark {
            display: grid;
            width: 52px;
            height: 52px;
            margin: 0 auto 18px;
            place-items: center;
            border-radius: 15px;
            background: linear-gradient(135deg, #2864ff, #1747c7);
            color: white;
            font-size: 22px;
            font-weight: 900;
          }

          .login-shell h1 {
            margin: 0;
            font-size: 30px;
          }

          .login-shell p {
            margin: 9px 0 0;
            color: var(--muted);
          }

          @media (max-width: 700px) {
            [data-testid="stMainBlockContainer"] {
              padding-top: 1rem;
            }

            .metric-card {
              min-height: auto;
            }

            .donut-layout {
              align-items: flex-start;
              flex-direction: column;
            }
          }
        </style>
        """
    )


def render_report_header(scan_time: str | None = None) -> None:
    """Render the compact report heading."""
    subtitle = (
        f"Scan completed on {scan_time}"
        if scan_time
        else "Enter a website in the sidebar to begin a new quality review."
    )
    st.html(
        f"""
        <section class="report-header">
          <h1>Website Typo Report</h1>
          <p>{html.escape(subtitle)}</p>
        </section>
        """
    )


def render_metric_card(label: str, value: str, note: str, domain: bool = False) -> None:
    """Render a styled summary card with escaped content."""
    value_class = "metric-value is-domain" if domain else "metric-value"
    st.html(
        f"""
        <article class="metric-card">
          <div class="metric-label">{html.escape(label)}</div>
          <div class="{value_class}">{html.escape(value)}</div>
          <div class="metric-note">{html.escape(note)}</div>
        </article>
        """
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

    st.html(
        """
        <section class="login-shell">
          <div class="login-mark">W</div>
          <h1>Website Typo Scanner</h1>
          <p>Enter the private access password to open the scanner.</p>
        </section>
        """
    )
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


def render_analytics(issues: list[dict[str, str]]) -> None:
    """Render three report analytics cards similar to the reference dashboard."""
    counts = Counter(issue["issue_type"] for issue in issues)
    page_counts = Counter(issue["page_url"] for issue in issues)
    total = len(issues)
    colors = {
        "Spelling Error": "#ff4d57",
        "Grammar / Wording": "#ffad33",
        "Repeated Words": "#7957d5",
        "Brand / Name Inconsistency": "#4a90ed",
    }

    angle = 0.0
    gradient_parts = []
    for issue_type in ALLOWED_ISSUE_TYPES:
        count = counts.get(issue_type, 0)
        if count:
            next_angle = angle + (count / total * 360)
            gradient_parts.append(
                f"{colors[issue_type]} {angle:.1f}deg {next_angle:.1f}deg"
            )
            angle = next_angle
    gradient = ", ".join(gradient_parts) or "#e9edf4 0deg 360deg"

    legend = "".join(
        f"""
        <div class="legend-item">
          <span class="legend-dot" style="background:{colors[issue_type]}"></span>
          <span>{html.escape(issue_type)}</span>
          <strong>{counts.get(issue_type, 0)}</strong>
        </div>
        """
        for issue_type in sorted(
            ALLOWED_ISSUE_TYPES,
            key=lambda name: counts.get(name, 0),
            reverse=True,
        )
    )

    max_page_count = max(page_counts.values(), default=1)
    bars = "".join(
        f"""
        <div class="bar-item">
          <div class="bar-label" title="{html.escape(url, quote=True)}">
            {html.escape(urlsplit(url).path or "/")}
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:{count / max_page_count * 100:.1f}%"></div>
          </div>
          <div class="bar-count">{count}</div>
        </div>
        """
        for url, count in page_counts.most_common(8)
    ) or '<div class="section-copy">No issues to chart.</div>'

    percentages = "".join(
        f"""
        <div class="legend-item">
          <span class="legend-dot" style="background:{colors[issue_type]}"></span>
          <span>{html.escape(issue_type)}</span>
          <strong>{(counts.get(issue_type, 0) / max(total, 1) * 100):.0f}%</strong>
        </div>
        """
        for issue_type in sorted(
            ALLOWED_ISSUE_TYPES,
            key=lambda name: counts.get(name, 0),
            reverse=True,
        )
    )

    overview, pages, top_types = st.columns([1, 1.15, 1])
    with overview:
        st.html(
            f"""
            <section class="dashboard-card">
              <h3>Overview</h3>
              <div class="donut-layout">
                <div class="donut" style="background:conic-gradient({gradient})">
                  <div class="donut-center">
                    <div><strong>{total}</strong><span>Total issues</span></div>
                  </div>
                </div>
                <div class="chart-legend">{legend}</div>
              </div>
            </section>
            """
        )
    with pages:
        st.html(
            f"""
            <section class="dashboard-card">
              <h3>Issues by Page</h3>
              {bars}
            </section>
            """
        )
    with top_types:
        st.html(
            f"""
            <section class="dashboard-card">
              <h3>Top Issue Types</h3>
              <div class="donut-layout">
                <div class="donut" style="background:conic-gradient({gradient})">
                  <div class="donut-center">
                    <div><strong>{total}</strong><span>Flagged</span></div>
                  </div>
                </div>
                <div class="chart-legend">{percentages}</div>
              </div>
            </section>
            """
        )


def result_table(issues: list[dict[str, str]]) -> None:
    """Render a styled HTML issue table matching the report dashboard."""
    if not issues:
        st.success("No issues were found in the scanned copy.")
        return

    rows = ""
    for index, issue in enumerate(issues, start=1):
        context = html.escape(issue["context_sentence"])
        typo = html.escape(issue["typo_found"])
        if issue["typo_found"]:
            context = re.sub(
                re.escape(typo),
                f'<span class="context-hit">{typo}</span>',
                context,
                flags=re.IGNORECASE,
            )
        safe_url = html.escape(issue["page_url"], quote=True)
        rows += f"""
        <tr>
          <td>{index}</td>
          <td><a href="{safe_url}" target="_blank">{html.escape(issue["page_url"])}</a></td>
          <td><span class="error-pill">{typo}</span></td>
          <td>{context}</td>
          <td><span class="fix-pill">{html.escape(issue["suggested_fix"])}</span></td>
          <td><span class="type-pill">{html.escape(issue["issue_type"])}</span></td>
        </tr>
        """

    st.html(
        f"""
        <div class="results-shell">
          <table class="results-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Page URL</th>
                <th>Issue Found</th>
                <th>Context Sentence</th>
                <th>Suggested Fix</th>
                <th>Issue Type</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
        </div>
        """
    )


inject_styles()
require_optional_password()

with st.sidebar:
    st.html(
        """
        <div class="sidebar-brand">
          <strong>Website Typo Scanner</strong>
          <span>Copy quality dashboard</span>
        </div>
        <div class="sidebar-section-label">Scan target</div>
        """
    )
    url_preset = st.selectbox(
        "Quick URL",
        ["Custom website", "Modern Medicine Group", "Example website"],
        help="Choose a saved example or enter any public website below.",
    )
    preset_urls = {
        "Modern Medicine Group": "https://themodernmedicinegroup.com",
        "Example website": "https://example.com",
    }
    default_url = preset_urls.get(
        url_preset,
        st.session_state.get("last_target_url", "https://themodernmedicinegroup.com"),
    )
    target_url = st.text_input(
        "Website URL",
        value=default_url,
        placeholder="https://example.com",
        help="Include https:// at the beginning.",
    )
    st.session_state.last_target_url = target_url
    st.html('<div class="sidebar-section-label">Scan options</div>')
    scan_mode = st.radio(
        "Analysis mode",
        ["Live AI scan", "Demo preview"],
        index=0 if get_secret("OPENAI_API_KEY") else 1,
        help="Demo preview uses sample data and makes no API call.",
    )
    demo_mode = scan_mode == "Demo preview"
    page_limit = st.slider("Maximum pages", 1, MAX_PAGES, min(10, MAX_PAGES))
    show_report_preview = st.toggle(
        "Show report preview",
        value=True,
        help="Display the full downloadable HTML report inside the app.",
    )
    scan_clicked = st.button("Scan Website", type="primary", width="stretch")
    if st.button("Clear current results", width="stretch"):
        st.session_state.pop("scan_result", None)
        st.rerun()

    st.divider()
    st.html(
        f"""
        <div class="model-card">
          <span>Active AI model</span>
          <strong>{html.escape(OPENAI_MODEL)}</strong>
        </div>
        """
    )
    api_status = "Connected" if get_secret("OPENAI_API_KEY") else "Demo only"
    st.caption(f"API status: {api_status}")
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
        "scan_time": datetime.now().astimezone().strftime("%B %d, %Y at %I:%M %p"),
    }
    status.success("Scan complete.")

if result := st.session_state.get("scan_result"):
    render_report_header(result.get("scan_time"))
    summary_columns = st.columns(4)
    with summary_columns[0]:
        render_metric_card(
            "Website",
            urlsplit(result["url"]).netloc,
            "Public website scanned",
            domain=True,
        )
    with summary_columns[1]:
        render_metric_card(
            "Pages Scanned",
            str(result["pages_scanned"]),
            "Internal pages reviewed",
        )
    with summary_columns[2]:
        render_metric_card(
            "Issues Found",
            str(len(result["issues"])),
            "Items ready for review",
        )
    with summary_columns[3]:
        render_metric_card(
            "Status",
            "Completed",
            "Demo data" if result["demo_mode"] else "Live AI analysis",
        )

    render_analytics(result["issues"])

    st.html(
        """
        <div class="section-heading">Issues Found</div>
        <div class="section-copy">
          Review each flagged item before updating the website copy.
        </div>
        """
    )
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

    result_table(result["issues"])
    if show_report_preview:
        with st.expander("Open full HTML report preview"):
            st.html(result["html"])
else:
    render_report_header()
    st.html(
        """
        <section class="empty-dashboard">
          <strong>Your report will appear here</strong>
          <span>Choose a URL and scan mode in the sidebar, then start the scan.</span>
        </section>
        """
    )
