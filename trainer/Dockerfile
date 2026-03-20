FROM python:3.11-slim

WORKDIR /trainer

COPY requirements.txt /trainer/requirements.txt
RUN pip install --no-cache-dir -r /trainer/requirements.txt

COPY scheduler.py /trainer/scheduler.py

CMD ["python", "/trainer/scheduler.py"]

