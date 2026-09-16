# A slim Python base image keeps the container small
FROM python:3.11-slim

WORKDIR /app

# Have Docker cache the installed dependencies
# So that if you change your code but not your dependencies, 
# Docker will reuse the cached layer and skip reinstalling everything.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the backend code
COPY . .

EXPOSE 8000

# --reload watches for file changes and restarts automatically.
# Combined with the bind-mount volume in docker-compose.yml,
# so editing main.py updates the running container immediately
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]