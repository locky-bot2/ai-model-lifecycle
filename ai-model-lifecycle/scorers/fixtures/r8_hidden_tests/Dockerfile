# The r8 hidden-test runner: Python + psycopg, nothing else (HTTP is stdlib).
FROM python:3.12-slim
RUN pip install --no-cache-dir "psycopg[binary]==3.2.3"
WORKDIR /tests
ENTRYPOINT ["python", "/tests/runner.py"]
