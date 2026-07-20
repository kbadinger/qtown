FROM caddy:2-alpine

WORKDIR /srv
COPY index.html base.css style.css app.js /srv/
COPY Caddyfile /etc/caddy/Caddyfile

# Run as a non-root user (Trivy DS-0002). Point Caddy's storage at a writable dir.
ENV XDG_DATA_HOME=/tmp XDG_CONFIG_HOME=/tmp
RUN adduser -D -u 10001 appuser
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:${PORT:-8080}/ > /dev/null || exit 1

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
