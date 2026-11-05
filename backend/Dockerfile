FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Wersja wdrożenia dla /api/przeszlosc/wersja/ (kontener nie ma .git); puste = nieznana
ARG GIT_COMMIT=
ARG BUILD_TIME=
ENV GIT_COMMIT=$GIT_COMMIT BUILD_TIME=$BUILD_TIME
RUN USE_SQLITE=true DJANGO_DEBUG=true python manage.py collectstatic --noinput
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
