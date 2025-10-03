FROM python:3.13-slim

WORKDIR /indirector
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Hot-reload
RUN pip install --no-cache-dir watchdog[watchmedo]
CMD ["watchmedo", "auto-restart", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "main.py"]
