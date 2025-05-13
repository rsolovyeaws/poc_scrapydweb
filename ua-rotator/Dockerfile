FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app.py .

# Create data directory for persistent storage
RUN mkdir -p /data
VOLUME /data

# Set environment variables
ENV PORT=5000
ENV HOST=0.0.0.0
ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

# Expose the port
EXPOSE 5000

# Run the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app", "--workers", "2", "--log-level", "info"] 