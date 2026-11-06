FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 ARTIFACT_DIR=/srv/artifacts

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/docker-entrypoint.sh .
COPY data ./data

# Dataset used to train the model (override with --build-arg or the environment in docker-compose.yml).
ARG TRAIN_CSV=/srv/data/cardiovascular_disease_dataset.csv
ARG TRAIN_TARGET=target
ARG TRAIN_ID_COLUMNS=patientid
ARG TRAIN_DROP_COLUMNS=
ARG TRAIN_PROFILE=heart13
ENV TRAIN_CSV=$TRAIN_CSV TRAIN_TARGET=$TRAIN_TARGET TRAIN_ID_COLUMNS=$TRAIN_ID_COLUMNS \
    TRAIN_DROP_COLUMNS=$TRAIN_DROP_COLUMNS TRAIN_PROFILE=$TRAIN_PROFILE

# Train inside the image so the saved model always matches the library versions that serve it.
RUN mkdir -p /srv/artifacts && \
    python -m app.cli train --csv "$TRAIN_CSV" --target "$TRAIN_TARGET" \
      ${TRAIN_ID_COLUMNS:+--id-columns $TRAIN_ID_COLUMNS} \
      ${TRAIN_DROP_COLUMNS:+--drop-columns $TRAIN_DROP_COLUMNS} \
      --profile "$TRAIN_PROFILE" --threshold-strategy youden

RUN useradd -m api && chown -R api /srv && chmod +x docker-entrypoint.sh
USER api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health')"
ENTRYPOINT ["./docker-entrypoint.sh"]
