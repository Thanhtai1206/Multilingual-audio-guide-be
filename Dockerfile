FROM python:3.14.7-slim

WORKDIR /code

# Copy requirements trước để Docker cache lớp cài thư viện (đổi code không phải cài lại)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]