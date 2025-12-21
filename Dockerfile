FROM python:3.11-slim

# Prevent Python buffering issues
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Upgrade pip + build tooling FIRST (critical on Synology)
RUN pip install --upgrade pip setuptools wheel

# Copy requirements
COPY requirements.txt .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "heresy_campaign/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
