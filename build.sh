#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Set Playwright path to the project directory so Render copies it to the runtime environment
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/.playwright

# Install Chromium for Playwright
playwright install chromium
playwright install-deps chromium
