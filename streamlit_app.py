"""Interactive Streamlit dashboard for Website Typo Scanner."""

from __future__ import annotations

import html
import ipaddress
import inspect
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

          /* Minimal dark dashboard theme inspired by the supplied reference. */
          :root {
            --ink: #17151d;
            --muted: #77737f;
            --line: #e7e4ea;
            --blue: #a695e8;
            --blue-dark: #7665c0;
            --surface: #fbfafb;
            --canvas: #aaa8ad;
            --green: #8fcf62;
            --red: #f0645d;
            --lavender: #a99add;
            --lime: #bce998;
            --shell: #111111;
            --panel-dark: #211f27;
          }

          .stApp {
            background: #aaa8ad;
          }

          [data-testid="stHeader"] {
            height: 2.4rem;
            background: transparent;
          }

          [data-testid="stAppViewContainer"] > .main {
            margin: 28px 34px 34px 0;
            overflow: hidden;
            border-radius: 0 22px 22px 0;
            background:
              radial-gradient(circle at 5% 0%, rgba(139, 75, 43, .36), transparent 25rem),
              #111111;
            box-shadow: 0 26px 70px rgba(24, 20, 28, .28);
          }

          [data-testid="stMainBlockContainer"] {
            max-width: 1500px;
            padding: 2.2rem 2.3rem 3rem;
          }

          [data-testid="stSidebar"] {
            margin: 28px 0 34px 34px;
            border: 0;
            border-radius: 22px 0 0 22px;
            background:
              radial-gradient(circle at 0% 0%, rgba(136, 72, 41, .52), transparent 20rem),
              #111111;
            box-shadow: -12px 26px 70px rgba(24, 20, 28, .22);
          }

          [data-testid="stSidebarContent"] {
            padding: 1.4rem 1rem 1.4rem;
          }

          [data-testid="stSidebar"] label,
          [data-testid="stSidebar"] p,
          [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #aaa6af;
          }

          [data-testid="stSidebar"] [data-baseweb="input"] > div,
          [data-testid="stSidebar"] [data-baseweb="select"] > div {
            border-color: #343139;
            background: #211f27;
          }

          [data-testid="stSidebar"] input {
            color: #f6f4f7;
          }

          [data-testid="stSidebar"] [role="radiogroup"] {
            gap: 5px;
            padding: 5px;
            border: 1px solid #302d35;
            border-radius: 13px;
            background: #1c1a20;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label {
            padding: 6px 8px;
            border-radius: 9px;
          }

          [data-testid="stSidebar"] hr {
            border-color: #302d35;
          }

          .sidebar-brand {
            margin: -4px -1px 12px;
            padding: 18px 16px;
            border: 1px solid rgba(255, 255, 255, .06);
            border-radius: 16px;
            background: rgba(255, 255, 255, .035);
            box-shadow: none;
          }

          .sidebar-brand strong {
            color: #f8f6f8;
            font-size: 18px;
          }

          .sidebar-brand span {
            color: #9e99a5;
          }

          .sidebar-section-label {
            color: #77727e;
          }

          .model-card {
            border-color: #343139;
            background: #211f27;
          }

          .model-card span {
            color: #85808b;
          }

          .model-card strong {
            color: #d8f1b9;
          }

          .stButton > button[kind="primary"] {
            border-radius: 12px;
            background: #f7f5f7;
            box-shadow: none;
            color: #151318;
          }

          .stButton > button[kind="primary"]:hover {
            background: var(--lime);
            box-shadow: none;
            color: #151318;
          }

          [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
            border-color: #37333c;
            background: #211f27;
            color: #beb9c3;
          }

          .report-header {
            margin: 2px 0 24px;
            text-align: left;
          }

          .report-header h1 {
            color: #faf8fa;
            font-size: clamp(34px, 4vw, 52px);
          }

          .report-header p {
            color: #99949f;
            font-size: 14px;
          }

          .metric-card {
            min-height: 112px;
            border-color: rgba(255, 255, 255, .08);
            border-radius: 16px;
            background: #211f27;
            box-shadow: none;
          }

          .metric-label {
            color: #8f8995;
          }

          .metric-value {
            color: #f8f6f8;
          }

          .metric-value.is-domain {
            color: #c8bdf1;
          }

          .metric-note {
            color: #77727e;
          }

          .dashboard-card {
            min-height: 310px;
            border: 0;
            border-radius: 18px;
            background: #f8f7f8;
            box-shadow: none;
          }

          .dashboard-card h3 {
            color: #1b181f;
            font-size: 17px;
          }

          .donut-center {
            background: #f8f7f8;
            box-shadow: inset 0 0 0 1px #e5e1e7;
          }

          .bar-track {
            background: #e8e5ea;
          }

          .bar-fill {
            background: linear-gradient(90deg, #a99add, #c3b8eb);
          }

          .section-heading {
            color: #f8f6f8;
          }

          .section-copy {
            color: #8e8994;
          }

          .stDownloadButton > button {
            border-color: #39353e;
            background: #211f27;
            color: #e5e1e7;
          }

          .stDownloadButton > button:hover {
            border-color: #a99add;
            color: #ffffff;
          }

          .results-shell {
            border: 0;
            border-radius: 18px;
            background: #f8f7f8;
            box-shadow: none;
          }

          .results-table th {
            background: #211f27;
            color: #f8f6f8;
          }

          .results-table td {
            border-color: #e8e5ea;
            color: #625e68;
          }

          .results-table a {
            color: #7761c5;
          }

          .error-pill, .type-pill {
            background: #fde9e7;
            color: #c94d47;
          }

          .fix-pill {
            background: #e9f6df;
            color: #4c8c2d;
          }

          .context-hit {
            color: #d1554e;
          }

          .empty-dashboard {
            border-color: #343139;
            background: #211f27;
          }

          .empty-dashboard strong {
            color: #f8f6f8;
          }

          .empty-dashboard span {
            color: #8e8994;
          }

          [data-testid="stAlert"] {
            border: 1px solid #38343c;
            background: #211f27;
            color: #d8d4dc;
          }

          [data-testid="stExpander"] {
            border-color: #38343c;
            border-radius: 16px;
            background: #211f27;
          }

          [data-testid="stExpander"] summary {
            color: #e2dee5;
          }

          @media (max-width: 900px) {
            [data-testid="stAppViewContainer"] > .main {
              margin: 10px;
              border-radius: 18px;
            }

            [data-testid="stSidebar"] {
              margin: 0;
              border-radius: 0;
            }

            [data-testid="stMainBlockContainer"] {
              padding: 1.4rem 1rem 2rem;
            }
          }

          /* Final light glass theme. Kept last so it remains stable in cloud builds. */
          :root {
            --ink: #101314;
            --muted: #7a8283;
            --line: rgba(178, 190, 190, .34);
            --blue: #9fd941;
            --blue-dark: #78b51b;
            --surface: rgba(255, 255, 255, .82);
            --canvas: #e6eef0;
            --green: #7ebc23;
            --red: #ef625d;
            --lavender: #a6b6bd;
            --lime: #b9ec63;
            --shell: rgba(246, 249, 249, .88);
            --panel-dark: #8c9b9b;
          }

          .stApp {
            background:
              radial-gradient(circle at 16% 5%, rgba(255,255,255,.98), transparent 24rem),
              radial-gradient(circle at 90% 18%, rgba(184,202,231,.58), transparent 32rem),
              linear-gradient(145deg, #edf4f3 0%, #dbe6eb 48%, #bccde0 100%);
            color: var(--ink);
          }

          [data-testid="stHeader"] {
            height: 2.8rem;
            background: transparent;
          }

          [data-testid="stAppViewContainer"] > .main {
            margin: 24px 28px 28px 0;
            overflow: visible;
            border: 1px solid rgba(255,255,255,.82);
            border-left: 0;
            border-radius: 0 26px 26px 0;
            background: rgba(245, 249, 249, .79);
            box-shadow: 0 24px 70px rgba(69, 88, 97, .16);
            backdrop-filter: blur(24px);
          }

          [data-testid="stMainBlockContainer"] {
            max-width: 1500px;
            padding: 2.2rem 2.4rem 3rem;
          }

          [data-testid="stSidebar"] {
            margin: 24px 0 28px 28px;
            border: 1px solid rgba(255,255,255,.82);
            border-right: 1px solid rgba(186,198,200,.28);
            border-radius: 26px 0 0 26px;
            background: rgba(248, 251, 250, .9);
            box-shadow: -14px 24px 70px rgba(69, 88, 97, .13);
            backdrop-filter: blur(24px);
          }

          [data-testid="stSidebarContent"] {
            padding: 1.35rem 1rem 1.5rem;
          }

          [data-testid="stSidebar"] label,
          [data-testid="stSidebar"] p,
          [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #6f7879;
          }

          [data-testid="stSidebar"] [data-baseweb="input"] > div,
          [data-testid="stSidebar"] [data-baseweb="select"] > div {
            border-color: rgba(166,180,181,.42);
            background: rgba(255,255,255,.86);
            box-shadow: 0 5px 16px rgba(92,108,110,.055);
          }

          [data-testid="stSidebar"] input {
            color: #15191a;
          }

          [data-testid="stSidebar"] [role="radiogroup"] {
            gap: 4px;
            padding: 5px;
            border: 1px solid rgba(166,180,181,.35);
            border-radius: 13px;
            background: rgba(236,241,240,.82);
          }

          [data-testid="stSidebar"] [role="radiogroup"] label {
            padding: 6px 8px;
            border-radius: 9px;
            color: #555e5f;
          }

          [data-testid="stSidebar"] hr {
            border-color: rgba(175,188,189,.3);
          }

          .sidebar-brand {
            margin: -4px -1px 12px;
            padding: 18px 16px;
            border: 1px solid rgba(181,195,195,.35);
            border-radius: 17px;
            background:
              radial-gradient(circle at 92% 15%, rgba(185,236,99,.42), transparent 7rem),
              rgba(255,255,255,.74);
            box-shadow: 0 12px 28px rgba(86,102,104,.08);
          }

          .sidebar-brand strong {
            color: #111516;
            font-size: 19px;
          }

          .sidebar-brand span {
            color: #778081;
          }

          .sidebar-section-label {
            color: #8a9393;
          }

          .model-card {
            border-color: rgba(166,180,181,.36);
            background: rgba(255,255,255,.68);
          }

          .model-card span {
            color: #929a9a;
          }

          .model-card strong {
            color: #568411;
          }

          .stButton > button[kind="primary"] {
            border: 1px solid #91c737;
            border-radius: 12px;
            background: linear-gradient(135deg, #c5ef79, #a3dd49);
            box-shadow: 0 10px 22px rgba(119,166,45,.18);
            color: #17200d;
          }

          .stButton > button[kind="primary"]:hover {
            background: #b8e766;
            box-shadow: 0 12px 26px rgba(119,166,45,.24);
            color: #10170a;
          }

          [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
            border-color: rgba(166,180,181,.42);
            background: rgba(255,255,255,.7);
            color: #5f6868;
          }

          .report-header {
            margin: 2px 0 24px;
            text-align: left;
          }

          .report-header h1 {
            color: #111516;
            font-size: clamp(35px, 4vw, 52px);
            font-weight: 650;
            letter-spacing: -.055em;
          }

          .report-header p {
            color: #7d8687;
          }

          .metric-card {
            min-height: 112px;
            border: 1px solid rgba(173,187,188,.33);
            border-radius: 17px;
            background: rgba(255,255,255,.75);
            box-shadow: 0 12px 30px rgba(78,96,99,.07);
            backdrop-filter: blur(14px);
          }

          .metric-label {
            color: #8d9596;
          }

          .metric-value {
            color: #111516;
          }

          .metric-value.is-domain {
            color: #4f7f10;
          }

          .metric-note {
            color: #969e9f;
          }

          .dashboard-card {
            min-height: 310px;
            border: 1px solid rgba(173,187,188,.34);
            border-radius: 18px;
            background: rgba(255,255,255,.82);
            box-shadow: 0 14px 34px rgba(78,96,99,.075);
            backdrop-filter: blur(14px);
          }

          .dashboard-card h3 {
            color: #15191a;
          }

          .donut-center {
            background: #f9fbfa;
            box-shadow: inset 0 0 0 1px rgba(173,187,188,.35);
          }

          .bar-track {
            background: #e8eeee;
          }

          .bar-fill {
            background: linear-gradient(90deg, #9ed63f, #c4ed79);
          }

          .section-heading {
            color: #15191a;
          }

          .section-copy {
            color: #7d8687;
          }

          .stDownloadButton > button {
            border-color: rgba(166,180,181,.42);
            background: rgba(255,255,255,.74);
            color: #303637;
          }

          .stDownloadButton > button:hover {
            border-color: #9acb4a;
            background: rgba(247,252,241,.9);
            color: #38540e;
          }

          .results-shell {
            border: 1px solid rgba(173,187,188,.34);
            border-radius: 18px;
            background: rgba(255,255,255,.84);
            box-shadow: 0 14px 34px rgba(78,96,99,.075);
          }

          .results-table th {
            background: #15191a;
            color: #f8faf8;
          }

          .results-table td {
            border-color: #e8eeee;
            color: #60696a;
          }

          .results-table a {
            color: #527f15;
          }

          .error-pill, .type-pill {
            background: #feeeec;
            color: #c95049;
          }

          .fix-pill {
            background: #edf8df;
            color: #518527;
          }

          .context-hit {
            color: #d0544d;
          }

          .empty-dashboard {
            border-color: rgba(160,177,178,.48);
            background: rgba(255,255,255,.64);
          }

          .empty-dashboard strong {
            color: #15191a;
          }

          .empty-dashboard span {
            color: #7d8687;
          }

          [data-testid="stAlert"] {
            border: 1px solid rgba(166,180,181,.35);
            background: rgba(255,255,255,.74);
            color: #4d5657;
          }

          [data-testid="stExpander"] {
            border-color: rgba(166,180,181,.35);
            border-radius: 16px;
            background: rgba(255,255,255,.72);
          }

          [data-testid="stExpander"] summary {
            color: #353b3c;
          }

          @media (max-width: 900px) {
            [data-testid="stAppViewContainer"] > .main {
              margin: 8px;
              border: 1px solid rgba(255,255,255,.82);
              border-radius: 19px;
            }

            [data-testid="stSidebar"] {
              margin: 0;
              border-radius: 0;
            }

            [data-testid="stMainBlockContainer"] {
              padding: 1.35rem .95rem 2rem;
            }
          }

          /* Production layout refinements. */
          [data-testid="stSidebar"],
          [data-testid="stSidebar"] > div:first-child {
            width: 300px;
            min-width: 300px;
            max-width: 300px;
          }

          .dashboard-card {
            min-height: 290px;
            padding: 18px;
          }

          .donut-layout {
            min-height: 200px;
          }

          .donut {
            width: 132px;
            height: 132px;
          }

          .donut-center {
            width: 76px;
            height: 76px;
          }

          .production-note {
            margin-top: 10px;
            padding: 11px 12px;
            border: 1px solid rgba(159, 201, 82, .34);
            border-radius: 12px;
            background: rgba(241, 249, 227, .72);
            color: #64724d;
            font-size: 11px;
            line-height: 1.45;
          }

          @media (max-width: 900px) {
            [data-testid="stSidebar"],
            [data-testid="stSidebar"] > div:first-child {
              width: auto;
              min-width: auto;
              max-width: none;
            }
          }
          .url-hint {
            margin: -4px 0 2px;
            color: #8a9393;
            font-size: 10px;
            line-height: 1.4;
          }

          .connection-card {
            display: grid;
            grid-template-columns: 9px 1fr;
            gap: 9px;
            align-items: center;
            margin-top: 10px;
            padding: 11px 12px;
            border: 1px solid rgba(160, 190, 105, .35);
            border-radius: 12px;
            background: rgba(244, 250, 233, .75);
            color: #566746;
            font-size: 11px;
            font-weight: 650;
          }

          .connection-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #91c737;
            box-shadow: 0 0 0 4px rgba(145, 199, 55, .15);
          }

          [data-testid="stSidebar"] [data-testid="stExpander"] {
            border-color: rgba(166,180,181,.35);
            background: rgba(255,255,255,.48);
          }

          /* Sidebar state and transition fixes. */
          [data-testid="stSidebar"],
          [data-testid="stSidebar"] > div:first-child,
          [data-testid="stAppViewContainer"] > .main {
            transition:
              width .28s ease,
              min-width .28s ease,
              max-width .28s ease,
              margin .28s ease,
              border-radius .28s ease,
              opacity .2s ease,
              transform .28s ease;
          }

          [data-testid="stSidebar"][aria-expanded="true"],
          [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
            width: 300px;
            min-width: 300px;
            max-width: 300px;
          }

          [data-testid="stSidebar"][aria-expanded="false"] {
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            box-shadow: none !important;
            opacity: 0;
            overflow: hidden;
            transform: translateX(-18px);
          }

          [data-testid="stSidebar"][aria-expanded="false"] > div:first-child {
            width: 0 !important;
            min-width: 0 !important;
            max-width: 0 !important;
            padding: 0 !important;
            overflow: hidden;
          }

          body:has([data-testid="stSidebar"][aria-expanded="false"])
          [data-testid="stAppViewContainer"] > .main {
            margin: 24px 28px 28px !important;
            border: 1px solid rgba(255,255,255,.82) !important;
            border-radius: 26px !important;
          }

          body:has([data-testid="stSidebar"][aria-expanded="false"])
          [data-testid="stMainBlockContainer"] {
            max-width: 1540px;
            margin-inline: auto;
          }

          [data-testid="collapsedControl"] {
            top: 44px;
            left: 42px;
            z-index: 1000;
            border: 1px solid rgba(161,176,177,.4);
            border-radius: 12px;
            background: rgba(255,255,255,.86);
            box-shadow: 0 8px 22px rgba(74,92,95,.1);
            backdrop-filter: blur(14px);
          }

          @media (max-width: 900px) {
            body:has([data-testid="stSidebar"][aria-expanded="false"])
            [data-testid="stAppViewContainer"] > .main {
              margin: 8px !important;
              border-radius: 19px !important;
            }

            [data-testid="collapsedControl"] {
              top: 18px;
              left: 18px;
            }
          }

          /* Original blue-and-white dashboard theme. */
          :root {
            --ink: #13233f;
            --muted: #748096;
            --line: #e1e7f0;
            --blue: #2864f0;
            --blue-dark: #174fc8;
            --surface: #ffffff;
            --canvas: #f3f6fb;
            --green: #1d9b59;
            --red: #ff5964;
          }

          .stApp {
            background:
              radial-gradient(circle at 84% 4%, rgba(58, 112, 255, .07), transparent 28rem),
              #f3f6fb;
            color: var(--ink);
          }

          [data-testid="stAppViewContainer"] > .main {
            margin: 0;
            border: 0;
            border-radius: 0;
            background: transparent;
            box-shadow: none;
            backdrop-filter: none;
          }

          [data-testid="stMainBlockContainer"] {
            max-width: 1450px;
            padding: 2rem 2.3rem 3rem;
          }

          [data-testid="stSidebar"] {
            margin: 0;
            border: 0;
            border-right: 1px solid #e2e8f1;
            border-radius: 0;
            background: #ffffff;
            box-shadow: 12px 0 30px rgba(25, 48, 86, .045);
            backdrop-filter: none;
          }

          [data-testid="stSidebarContent"] {
            padding: 1.2rem .95rem 1.5rem;
          }

          [data-testid="stSidebar"] label,
          [data-testid="stSidebar"] p,
          [data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
            color: #69768c;
          }

          .sidebar-brand {
            margin: 0 0 14px;
            padding: 20px 18px;
            border: 0;
            border-radius: 18px;
            background: linear-gradient(135deg, #112e63 0%, #174fc8 100%);
            box-shadow: 0 14px 28px rgba(26, 72, 161, .22);
          }

          .sidebar-brand strong {
            color: #ffffff;
            font-size: 20px;
          }

          .sidebar-brand span {
            color: #c7d7f5;
          }

          .sidebar-section-label {
            color: #7c8799;
          }

          [data-testid="stSidebar"] [data-baseweb="input"] > div,
          [data-testid="stSidebar"] [data-baseweb="select"] > div {
            border-color: #dde4ef;
            background: #f7f9fd;
            box-shadow: none;
          }

          [data-testid="stSidebar"] input {
            color: #26344c;
          }

          [data-testid="stSidebar"] [data-testid="stExpander"] {
            border-color: #e1e7f0;
            background: #f8faff;
          }

          .stButton > button[kind="primary"] {
            border: 0;
            background: linear-gradient(135deg, #2f6bff, #1852d1);
            box-shadow: 0 10px 22px rgba(40, 100, 240, .24);
            color: #ffffff !important;
          }

          .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #2864f0, #1648bc);
            box-shadow: 0 12px 26px rgba(40, 100, 240, .3);
            color: #ffffff !important;
          }

          .stButton > button[kind="primary"] p,
          .stButton > button[kind="primary"] span,
          .stButton > button[kind="primary"] div {
            color: #ffffff !important;
            font-weight: 750 !important;
          }

          [data-testid="stSidebar"] [role="radiogroup"] {
            display: flex;
            gap: 4px;
            padding: 4px;
            border: 1px solid #dce3ed;
            border-radius: 13px;
            background: #f1f4f9;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label {
            display: flex;
            flex: 1 1 0;
            align-items: center;
            justify-content: center;
            min-height: 40px;
            margin: 0;
            padding: 8px 10px;
            border-radius: 9px;
            color: #66748a;
            font-weight: 700;
            text-align: center;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: #ffffff;
            color: #174fc8;
            box-shadow: 0 4px 12px rgba(25,48,86,.08);
          }

          [data-testid="stSidebar"] [role="radiogroup"] label p {
            margin: 0;
            color: inherit;
            line-height: 1.25;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {
            flex: 0 0 auto;
          }

          [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
            border-color: #dce3ed;
            background: #ffffff;
            color: #58667b;
          }

          .report-header {
            margin: 8px 0 30px;
            text-align: center;
          }

          .report-header h1 {
            color: #11213d;
            font-size: clamp(38px, 4vw, 56px);
            font-weight: 800;
            letter-spacing: -.055em;
          }

          .report-header p {
            color: #7c8799;
            font-size: 14px;
          }

          .metric-card {
            min-height: 124px;
            padding: 20px;
            border: 1px solid #e1e7f0;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 10px 28px rgba(25, 48, 86, .06);
            backdrop-filter: none;
          }

          .metric-label {
            color: #7a879c;
          }

          .metric-value {
            color: #13233f;
          }

          .metric-value.is-domain {
            color: #13233f;
          }

          .metric-note {
            color: #98a2b3;
          }

          .dashboard-card {
            min-height: 310px;
            padding: 20px;
            border: 1px solid #e1e7f0;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 10px 28px rgba(25, 48, 86, .06);
            backdrop-filter: none;
          }

          .dashboard-card h3 {
            color: #172641;
          }

          .donut-center {
            background: #ffffff;
            box-shadow: inset 0 0 0 1px #e1e7f0;
          }

          .bar-track {
            background: #edf1f7;
          }

          .bar-fill {
            background: linear-gradient(90deg, #ff5360, #ff747e);
          }

          .section-heading {
            color: #142440;
          }

          .section-copy {
            color: #7d899c;
          }

          .stDownloadButton > button {
            border-color: #dce3ed;
            background: #ffffff;
            color: #34445e;
          }

          .stDownloadButton > button:hover {
            border-color: #2f6bff;
            background: #f4f7ff;
            color: #174fc8;
          }

          .results-shell {
            border: 1px solid #e1e7f0;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 10px 28px rgba(25, 48, 86, .06);
          }

          .results-table th {
            background: #13233f;
            color: #ffffff;
          }

          .results-table td {
            border-color: #edf0f5;
            color: #5d6a7f;
          }

          .results-table a {
            color: #2464dc;
          }

          .empty-dashboard {
            border-color: #d7dfeb;
            background: rgba(255,255,255,.72);
          }

          .empty-dashboard strong {
            color: #142440;
          }

          .empty-dashboard span {
            color: #7d899c;
          }

          .model-card {
            border-color: #e1e7f0;
            background: #f7f9fd;
          }

          .model-card span {
            color: #8a95a7;
          }

          .model-card strong {
            color: #162a4d;
          }

          .connection-card {
            border-color: #d9e6fb;
            background: #f2f7ff;
            color: #31598c;
          }

          .connection-dot {
            background: #2f6bff;
            box-shadow: 0 0 0 4px rgba(47, 107, 255, .13);
          }

          .production-note {
            border-color: #e0e6f0;
            background: #f8faff;
            color: #748096;
          }

          [data-testid="stAlert"] {
            border-color: #dfe6ef;
            background: #ffffff;
            color: #536177;
          }

          body:has([data-testid="stSidebar"][aria-expanded="false"])
          [data-testid="stAppViewContainer"] > .main {
            margin: 0 !important;
            border: 0 !important;
            border-radius: 0 !important;
          }

          [data-testid="collapsedControl"] {
            top: 20px;
            left: 20px;
            border-color: #dce3ed;
            background: #ffffff;
            box-shadow: 0 8px 22px rgba(25,48,86,.1);
          }

          @media (max-width: 900px) {
            [data-testid="stMainBlockContainer"] {
              padding: 1.35rem .95rem 2rem;
            }

            body:has([data-testid="stSidebar"][aria-expanded="false"])
            [data-testid="stAppViewContainer"] > .main {
              margin: 0 !important;
            }
          }

          /* Cloud-safe control colors and readable labels. */
          [data-testid="stSidebar"] [role="radiogroup"] {
            display: grid !important;
            grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
            gap: 5px !important;
            padding: 5px !important;
            border: 1px solid #dce3ed !important;
            border-radius: 13px !important;
            background: #f1f4f9 !important;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label {
            display: flex !important;
            min-width: 0 !important;
            min-height: 44px !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 7px !important;
            margin: 0 !important;
            padding: 8px !important;
            border-radius: 9px !important;
            background: transparent !important;
            color: #627087 !important;
            text-align: center !important;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label p,
          [data-testid="stSidebar"] [role="radiogroup"] label span,
          [data-testid="stSidebar"] [role="radiogroup"] label div {
            color: #627087 !important;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background: #ffffff !important;
            box-shadow: 0 4px 12px rgba(25,48,86,.08) !important;
          }

          [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p,
          [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) span,
          [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) div {
            color: #174fc8 !important;
          }

          [data-testid="stSidebar"] [role="radiogroup"] input {
            accent-color: #2864f0 !important;
          }

          [data-testid="stSidebar"] [data-testid="stSegmentedControl"] {
            padding: 4px !important;
            border: 1px solid #dce3ed !important;
            border-radius: 13px !important;
            background: #f1f4f9 !important;
          }

          [data-testid="stSidebar"] [data-testid="stSegmentedControl"] button {
            min-width: 0 !important;
            min-height: 40px !important;
            border-color: transparent !important;
            border-radius: 8px !important;
            background: transparent !important;
            color: #627087 !important;
          }

          [data-testid="stSidebar"] [data-testid="stSegmentedControl"]
          button[aria-pressed="true"] {
            border-color: #2864f0 !important;
            background: #ffffff !important;
            color: #174fc8 !important;
            box-shadow: 0 4px 12px rgba(25,48,86,.08) !important;
          }

          [data-testid="stSidebar"] [data-testid="stSlider"] div[role="slider"] {
            border-color: #2864f0 !important;
            background: #2864f0 !important;
          }

          [data-testid="stSidebar"] [data-testid="stSlider"]
          div[data-baseweb="slider"] > div > div {
            background-color: #2864f0;
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
    url = url.strip()
    if url and "://" not in url:
        url = f"https://{url}"
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

ACTIVE_OPENAI_MODEL = get_secret("OPENAI_MODEL") or OPENAI_MODEL

with st.sidebar:
    st.html(
        """
        <div class="sidebar-brand">
          <strong>Website Typo Scanner</strong>
          <span>Copy quality dashboard</span>
        </div>
        <div class="sidebar-section-label">New scan</div>
        """
    )
    target_url = st.text_input(
        "Website URL",
        value=st.session_state.get(
            "last_target_url", "https://themodernmedicinegroup.com"
        ),
        placeholder="https://example.com",
        help="Enter a domain or complete public URL. HTTPS is added automatically.",
    )
    st.html(
        '<div class="url-hint">Example: example.com or https://example.com</div>'
    )
    st.session_state.last_target_url = target_url
    st.html('<div class="sidebar-section-label">Scan options</div>')
    scan_mode = st.selectbox(
        "Analysis mode",
        options=["AI Scan", "Demo Preview"],
        index=0 if get_secret("OPENAI_API_KEY") else 1,
        help="AI Scan uses your API key. Demo Preview uses sample data.",
    )
    demo_mode = scan_mode == "Demo Preview"
    page_limit = st.slider("Maximum pages", 1, MAX_PAGES, min(10, MAX_PAGES))
    crawl_depth = st.selectbox(
        "Crawl depth",
        options=[1, 2, 3],
        index=1,
        format_func=lambda depth: {
            1: "1 - Homepage links",
            2: "2 - Recommended",
            3: "3 - Deeper crawl",
        }[depth],
        help="Higher depth follows links farther from the homepage.",
    )
    with st.expander("Advanced options"):
        exclude_text = st.text_input(
            "Exclude URL paths",
            placeholder="/blog, /author, /privacy",
            help="Comma-separated path fragments that the crawler should skip.",
        )
        request_profile = st.selectbox(
            "Scan profile",
            ["Balanced", "Quick", "Thorough"],
            help="Adjusts the effective page count and crawl depth.",
        )
        st.caption(
            "Balanced is recommended. Quick scans fewer nearby pages; Thorough "
            "follows links deeper and may use more API tokens."
        )

    if request_profile == "Quick":
        effective_page_limit = min(page_limit, 5)
        effective_depth = 1
    elif request_profile == "Thorough":
        effective_page_limit = page_limit
        effective_depth = 3
    else:
        effective_page_limit = page_limit
        effective_depth = int(crawl_depth or 2)

    exclude_paths = [
        path.strip() for path in exclude_text.split(",") if path.strip()
    ]
    scan_clicked = st.button("Scan Website", type="primary", width="stretch")
    if st.button("Clear current results", width="stretch"):
        st.session_state.pop("scan_result", None)
        st.rerun()

    st.divider()
    st.html(
        f"""
        <div class="model-card">
          <span>Active AI model</span>
          <strong>{html.escape(ACTIVE_OPENAI_MODEL)}</strong>
        </div>
        """
    )
    api_connected = bool(get_secret("OPENAI_API_KEY"))
    if api_connected:
        st.html(
            """
            <div class="connection-card">
              <span class="connection-dot"></span>
              <span>OpenAI API connected and ready</span>
            </div>
            """
        )
    else:
        st.warning("OpenAI API key is not configured.")
    st.html(
        """
        <div class="production-note">
          Live scans use your private OpenAI API key. Each completed scan can be
          downloaded as an HTML dashboard or CSV file.
        </div>
        """
    )
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
            "OPENAI_API_KEY is not configured. Add it to your local .env file "
            "or Streamlit app secrets, or choose Demo Preview."
        )
        st.stop()

    progress = st.progress(0, text="Preparing scan...")
    status = st.empty()

    if demo_mode:
        status.info("Preparing sample report...")
        issues = get_demo_results(normalized_url)
        pages_scanned = len({issue["page_url"] for issue in issues})
        progress.progress(100, text="Demo preview ready")
    else:
        status.info("Crawling internal pages...")

        def update_crawl_progress(pages_found: int, current_url: str) -> None:
            percent = min(40, max(2, int(pages_found / effective_page_limit * 40)))
            progress.progress(
                percent,
                text=f"Collected {pages_found} page(s): {current_url}",
            )

        crawl_options = {
            "max_pages": effective_page_limit,
            "status_callback": update_crawl_progress,
        }
        supported_crawl_options = inspect.signature(crawl_website).parameters
        if "max_depth" in supported_crawl_options:
            crawl_options["max_depth"] = effective_depth
        if "exclude_paths" in supported_crawl_options:
            crawl_options["exclude_paths"] = exclude_paths

        pages = crawl_website(normalized_url, **crawl_options)
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
        analysis_failures: list[tuple[str, str]] = []

        def record_analysis_failure(page_url: str, message: str) -> None:
            analysis_failures.append((page_url, message))

        for index, page in enumerate(pages, start=1):
            progress_value = 40 + int(index / pages_scanned * 60)
            progress.progress(
                progress_value,
                text=f"Analyzing page {index} of {pages_scanned}",
            )
            issues.extend(
                analyze_text_with_ai(
                    client,
                    page["url"],
                    page["text"],
                    model=ACTIVE_OPENAI_MODEL,
                    error_callback=record_analysis_failure,
                )
            )

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
        "scan_time": datetime.now().astimezone().strftime("%B %d, %Y at %I:%M %p"),
        "scan_profile": request_profile,
        "demo_mode": demo_mode,
        "analysis_failures": analysis_failures if not demo_mode else [],
    }
    progress.empty()
    status.empty()
    st.toast("Scan complete. Your report is ready.")

if result := st.session_state.get("scan_result"):
    if result.get("analysis_failures"):
        failed_count = len(result["analysis_failures"])
        st.warning(
            f"{failed_count} page(s) could not be analyzed by the API. "
            "The report may be incomplete; check your model name, API billing, "
            "and Streamlit logs."
        )
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
            "Demo preview" if result["demo_mode"] else "Live AI analysis",
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
else:
    render_report_header()
    st.html(
        """
        <section class="empty-dashboard">
          <strong>Your report will appear here</strong>
          <span>Enter a public website URL in the sidebar, then start the scan.</span>
        </section>
        """
    )
