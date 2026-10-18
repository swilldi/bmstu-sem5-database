FROM postgres:17
RUN apt-get update \
    && apt-get install -y postgresql-plpython3-17 \
    && rm -rf /var/lib/apt/lists/*
