FROM python:3.12-slim
WORKDIR /app
COPY services/users/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/shared /shared
ENV PYTHONPATH=/shared
COPY services/users/main.py ./main.py
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
