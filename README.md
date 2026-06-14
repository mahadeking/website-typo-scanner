# Website Typo Scanner

A lightweight interactive Streamlit app that crawls a website's internal
pages, checks readable page copy with the OpenAI API, and creates:

- `typo_report.html` - a self-contained dashboard report
- `typo_report.csv` - a backup spreadsheet-friendly report

The app includes a website URL field, scan button, progress display, results
table, dashboard preview, and report download buttons. There is no database or
frontend build process.

## Requirements

- Python 3.10 or newer
- An internet connection for crawling and live AI analysis
- An OpenAI API key for live analysis

The crawler and report generation run locally. OpenAI API usage may incur
charges on your OpenAI API account. When no API key is configured, the script
creates a free demo report with sample results instead.

## 1. Install dependencies

Open PowerShell or Command Prompt in this folder and run:

```powershell
python -m pip install -r requirements.txt
```

## 2. Create your `.env` file

Copy `.env.example` to a new file named `.env`.

In PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder value:

```dotenv
OPENAI_API_KEY=your_real_api_key_here
OPENAI_MODEL=gpt-5.5
APP_PASSWORD=choose_a_private_access_password
```

Do not share or commit the `.env` file.

`APP_PASSWORD` is recommended before sharing a hosted app because it prevents
other people from using your OpenAI API key.

## 3. Run the interactive app

```powershell
python -m streamlit run streamlit_app.py
```

Your browser should open automatically. If it does not, open the local URL
shown in the terminal, normally:

```text
http://localhost:8501
```

Enter a public website URL, choose the page limit, and click **Scan Website**.
Use demo mode to test the interface without an API key.

## Command-line version

The original command-line workflow remains available:

```powershell
python typo_scanner.py
```

It scans the `BASE_URL` configured in `typo_scanner.py` and saves both reports
in this folder.

## Deploy free on Streamlit Community Cloud

1. Create a GitHub repository and upload this project.
2. Do not upload `.env`; it is excluded by `.gitignore`.
3. Sign in at <https://share.streamlit.io/>.
4. Click **Create app** and select your GitHub repository.
5. Set the main file path to `streamlit_app.py`.
6. Open **Advanced settings** and add these secrets:

```toml
OPENAI_API_KEY = "your_real_api_key_here"
OPENAI_MODEL = "gpt-5.5"
APP_PASSWORD = "choose_a_private_access_password"
```

7. Deploy the app and open the public URL Streamlit provides.

OpenAI API calls may incur charges even though Streamlit hosting can be free.
Keep `APP_PASSWORD` enabled so strangers cannot spend your API allowance.

## Notes

- AI suggestions should be reviewed by a person before website copy is changed.
- The hosted scanner blocks localhost, private, and reserved network addresses.
- Pages that block automated requests, require JavaScript rendering, or require
  authentication may not be readable by this lightweight crawler.
- Query strings are removed during URL normalization to prevent duplicate or
  unbounded crawling.
