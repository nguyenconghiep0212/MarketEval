# Create the virtual environment folder (.venv)
cd .\backend\
python -m venv .venv

# Activate the virtual environment
cd .\backend\
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install all pinned dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browser binaries (required for SPA scraping fallback)
playwright install chromium