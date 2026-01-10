FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
# Use Option 3: Full Vanna 2.0 Agent with all tools
# ChartGenerationTool and InsightsGenerationTool included
CMD ["uvicorn", "src.main_vanna2_full:app", "--host", "0.0.0.0", "--port", "8000"]
