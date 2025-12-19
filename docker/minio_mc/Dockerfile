FROM alpine:3.20

RUN apk add --no-cache curl dos2unix mc

COPY ./commands/setup_minio.sh /commands/setup_minio.sh
RUN dos2unix /commands/setup_minio.sh && chmod +x /commands/setup_minio.sh

CMD ["/bin/sh", "-c", "/commands/setup_minio.sh"]
