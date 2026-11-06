#!/bin/sh
# Starts the API. The model is normally trained while the image is built. If it is missing or cannot be
# loaded (for example after swapping the dataset through the environment), it is retrained here.
set -e

loadable() {
  python - <<'PY'
import sys
try:
    from app.service import CVDModelService
    CVDModelService()
except Exception as exc:  # noqa
    print("model check failed:", exc, file=sys.stderr)
    sys.exit(1)
PY
}

if ! loadable; then
  echo "Training model from ${TRAIN_CSV} (target ${TRAIN_TARGET}) ..."
  python -m app.cli train --csv "$TRAIN_CSV" --target "$TRAIN_TARGET" \
    ${TRAIN_ID_COLUMNS:+--id-columns $TRAIN_ID_COLUMNS} \
    ${TRAIN_DROP_COLUMNS:+--drop-columns $TRAIN_DROP_COLUMNS} \
    ${TRAIN_POSITIVE_LABEL:+--positive-label "$TRAIN_POSITIVE_LABEL"} \
    --profile "${TRAIN_PROFILE:-custom}" --threshold-strategy youden
fi
exec uvicorn app.main:get_app --factory --host 0.0.0.0 --port 8000
