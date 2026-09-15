# Build context is the repo root (see docker-compose.yml), because the
# dashboard imports analytics/scripts/{db,metrics}.py directly and reads
# data_quality/quality_report.csv - both live outside dashboard/.

FROM python:3.12-slim
WORKDIR /app

COPY dashboard/requirements.txt dashboard/requirements.txt
RUN pip install --no-cache-dir -r dashboard/requirements.txt

COPY analytics/scripts analytics/scripts
COPY data_quality/quality_report.csv data_quality/quality_report.csv
COPY dashboard dashboard

EXPOSE 8501
ENTRYPOINT ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
