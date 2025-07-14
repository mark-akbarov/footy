FROM python:3.13-bullseye as base

# Set environment variables
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

FROM base as builder

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc musl-dev libpq-dev libffi-dev zlib1g-dev g++ libev-dev git build-essential \
    ca-certificates mailcap debian-keyring debian-archive-keyring apt-transport-https \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install -U pip
RUN pip3 install pipenv=="2023.4.20"

COPY Pipfile .
COPY Pipfile.lock .

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base as runtime

WORKDIR /usr/src/app/

# Copy virtual environment from builder
COPY --from=builder /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

# Install runtime dependencies and clean up
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -g 1000 app && \
    useradd -r -u 1000 -g app app

RUN mkdir "/home/app" && chown -R app:app /home/app

# Copy application code with proper ownership and permissions
COPY --chown=app:app ./app /usr/src/app/
COPY --chown=app:app --chmod=755 app/entrypoint.sh /usr/src/app/entrypoint.sh

# Switch to non-root user
USER app

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
EXPOSE 8080
CMD [ "gunicorn", "main:app", "--workers", "8", "--worker-class", \
     "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080" ]
