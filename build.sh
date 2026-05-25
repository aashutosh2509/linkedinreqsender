#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install Chromium for Playwright
playwright install chromium
playwright install-deps chromium
