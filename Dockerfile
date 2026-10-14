# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (needed for compiling psycopg2 and some C extensions)
RUN apt-get update \
    && apt-get install -y gcc libpq-dev netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy project
COPY . /app/

# Expose port 8000
EXPOSE 8000

# Run entrypoint script (or we can just run gunicorn/runserver directly here)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
