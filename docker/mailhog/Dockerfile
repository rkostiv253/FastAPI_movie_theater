FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

RUN wget -O /usr/local/bin/MailHog \
      https://github.com/mailhog/MailHog/releases/download/v1.0.1/MailHog_linux_amd64 \
    && chmod +x /usr/local/bin/MailHog

COPY commands/setup_mailhog_auth.sh /commands/setup_mailhog_auth.sh
RUN dos2unix /commands/setup_mailhog_auth.sh && chmod +x /commands/setup_mailhog_auth.sh

# Use sh (exists) instead of bash (not installed)
CMD ["/bin/sh", "-c", "/commands/setup_mailhog_auth.sh && /usr/local/bin/MailHog"]
