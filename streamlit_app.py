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
