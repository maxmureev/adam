FROM python:3.13-alpine AS builder
RUN apk update && \
    apk upgrade && \
    apk add --no-cache build-base openldap-dev python3-dev libc6-compat

WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN pip install -U pip setuptools poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-root --no-interaction

COPY adam/ /build/adam/

FROM python:3.13-alpine
RUN apk add --no-cache libc6-compat openldap
WORKDIR /adam
ENV PYTHONPATH=/adam
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /build/adam/ /adam/
EXPOSE 8000
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8000", "--workers", "1", "--worker-class", "uvicorn.workers.UvicornWorker"]
