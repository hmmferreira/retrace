# Explicit experimental shared-auth image. The default Dockerfile remains legacy.
FROM debian:bookworm-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc AS protocol-source
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init . && git remote add origin https://github.com/parawanderer/FindMy.py \
    && git fetch --depth 1 origin 8ecfae6cb34b29caf0bd8176ee73155ca81415a8 \
    && test "$(git rev-parse FETCH_HEAD)" = 8ecfae6cb34b29caf0bd8176ee73155ca81415a8 \
    && git checkout --detach FETCH_HEAD \
    && git archive --format=tar HEAD findmy LICENSE.md > /tmp/protocol.tar \
    && echo '676e871098ec60a9c5e6718ea8cc18215631b036b99117a814ac1eb87d4e99e7  /tmp/protocol.tar' | sha256sum -c - \
    && mkdir /export && tar -xf /tmp/protocol.tar -C /export
FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libssl3 libstdc++6 libseccomp2 libapparmor1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --home-dir /data/retrace/home --no-create-home retrace
COPY requirements.lock requirements-shared.lock /app/
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r /app/requirements.lock -r /app/requirements-shared.lock \
    && pip check
COPY --from=protocol-source /export/ /opt/retrace-protocol/
COPY rootfs/app /app
RUN python -c "import json; from pathlib import Path; Path('/app/retrace/shared_backend.json').write_text(json.dumps({'revision':'8ecfae6cb34b29caf0bd8176ee73155ca81415a8','archive_sha256':'676e871098ec60a9c5e6718ea8cc18215631b036b99117a814ac1eb87d4e99e7'}))"
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/opt/retrace-protocol:/app
# No Rust exporter, remote signer, or runtime executable download helper here.
CMD ["python", "/app/bootstrap.py"]
