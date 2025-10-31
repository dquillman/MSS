ARG N8N_VERSION=latest
FROM n8nio/n8n:${N8N_VERSION}

# Copy workflows into image so we can auto-import on first boot
COPY n8n/workflows /data/workflows

# Entry script: import workflows once, then start n8n
COPY docker/entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
