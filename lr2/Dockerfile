FROM python:3.14-alpine

RUN adduser -D appuser

WORKDIR /home/appuser/init_service

COPY init_service/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser init_service/ .

USER appuser

ENTRYPOINT ["python", "main.py"]