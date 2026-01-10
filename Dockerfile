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
# Use Option 2: Vanna 2.0 with conversation history
# Option 3 (main_vanna2_full) has ToolContext validation issues with AgentMemory
# TODO: Fix PgVectorAgentMemory to properly inherit from vanna.core.memory.AgentMemory
CMD ["uvicorn", "src.main_vanna2:app", "--host", "0.0.0.0", "--port", "8000"]
