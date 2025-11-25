FROM nginx:1.25-alpine

# Remove default nginx configuration
RUN rm /etc/nginx/nginx.conf

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy custom error pages
COPY errors /usr/share/nginx/html/errors

# Create directory for SSL certificates
RUN mkdir -p /etc/nginx/ssl

# Create directory for Let's Encrypt challenges
RUN mkdir -p /var/www/certbot

# Set proper permissions
RUN chown -R nginx:nginx /var/www/certbot && \
    chown -R nginx:nginx /usr/share/nginx/html/errors

# Expose ports
EXPOSE 80 443

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
