FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Las dependencias van en su propia capa para aprovechar la caché entre builds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY mock_crm.py .

# El servicio no necesita privilegios de root.
RUN useradd --create-home servicio && chown servicio /srv
USER servicio

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
