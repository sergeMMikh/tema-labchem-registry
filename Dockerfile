FROM python:3.14-slim-trixie AS build

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt /build/
RUN python -m pip install --no-cache-dir --target=/runtime -r requirements.txt \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R 65532:65532 /app

FROM cgr.dev/chainguard/wolfi-base:latest

RUN apk add --no-cache python-3.14

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/runtime
ENV HOME=/app

WORKDIR /app

COPY --from=build --chown=65532:65532 /runtime /runtime
COPY --from=build --chown=65532:65532 /app/media /app/media
COPY --from=build --chown=65532:65532 /app/staticfiles /app/staticfiles
COPY --chown=65532:65532 . /app

USER 65532:65532

CMD ["python3.14", "-m", "waitress", "--listen=0.0.0.0:8000", "config.wsgi:application"]
