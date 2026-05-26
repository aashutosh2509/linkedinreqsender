#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Set Playwright path to the project directory so Render copies it to the runtime environment
export PLAYWRIGHT_BROWSERS_PATH=/opt/render/project/src/pw-browsers

# Install Chromium for Playwright
python -m playwright install chromium
python -m playwright install-deps chromium
