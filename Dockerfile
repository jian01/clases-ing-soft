# syntax=docker/dockerfile:1
FROM apache/airflow:3.2.2

USER airflow

COPY requirements.txt /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock

COPY dags/fraud_detection.py /opt/airflow/dags/fraud_detection.py
