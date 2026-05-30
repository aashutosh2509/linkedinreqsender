# Use the official Playwright Python image so browser dependencies and Chromium are already installed.
FROM mcr.microsoft.com/playwright/python:1.60.0

WORKDIR /app

# Install Python dependencies.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source into the container.
COPY . .

EXPOSE 5000

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
