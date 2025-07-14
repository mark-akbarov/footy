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
    ca-certificates mailcap debian-keyring debian-archive-keyring apt-transport-https

RUN pip3 install -U pip
RUN pip3 install pipenv=="2023.4.20"

COPY Pipfile .
COPY Pipfile.lock .

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM base as runtime

WORKDIR /usr/src/app/

COPY --from=builder /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

RUN groupadd -g 1000 app && \
    useradd -r -u 1000 -g app app

RUN mkdir "/home/app"
RUN	chown -R app:app /home/app

COPY ./app /usr/src/app/
RUN chown -R app:app /usr/src/app/

USER app

# Install the required netcat with apt-get
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd

COPY app/entrypoint.sh /usr/src/app/entrypoint.sh
RUN chmod +x /usr/src/app/entrypoint.sh

ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

EXPOSE 8000
CMD [ "gunicorn", "main:app", "--workers", "8", "--worker-class", \
		"uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080" ]