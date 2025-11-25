#!/bin/bash

# SSL/TLS Configuration Testing Script
# Tests SSL certificate validity, configuration, and security

set -e

echo "=========================================="
echo "SSL/TLS Configuration Test"
echo "=========================================="
echo ""

# Get domain name
if [ -z "$1" ]; then
    echo "Enter your domain name (e.g., example.com):"
    read -r DOMAIN
else
    DOMAIN="$1"
fi

if [ -z "$DOMAIN" ]; then
    echo "✗ Domain name is required"
    echo "Usage: $0 [domain]"
    exit 1
fi

echo "Testing SSL configuration for: $DOMAIN"
echo ""

# Test 1: Check if domain resolves
echo "Test 1: DNS Resolution"
echo "----------------------------------------"
if host "$DOMAIN" > /dev/null 2>&1; then
    IP=$(host "$DOMAIN" | grep "has address" | head -1 | awk '{print $4}')
    echo "✓ Domain resolves to: $IP"
else
    echo "✗ Domain does not resolve"
    echo "  Make sure DNS is configured correctly"
fi
echo ""

# Test 2: Check if ports are accessible
echo "Test 2: Port Accessibility"
echo "----------------------------------------"
if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$DOMAIN/80" 2>/dev/null; then
    echo "✓ Port 80 (HTTP) is accessible"
else
    echo "✗ Port 80 (HTTP) is not accessible"
fi

if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$DOMAIN/443" 2>/dev/null; then
    echo "✓ Port 443 (HTTPS) is accessible"
else
    echo "✗ Port 443 (HTTPS) is not accessible"
fi
echo ""

# Test 3: Check HTTP to HTTPS redirect
echo "Test 3: HTTP to HTTPS Redirect"
echo "----------------------------------------"
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -L "http://$DOMAIN" 2>/dev/null || echo "000")
if [ "$HTTP_RESPONSE" = "200" ]; then
    REDIRECT_URL=$(curl -s -o /dev/null -w "%{redirect_url}" "http://$DOMAIN" 2>/dev/null || echo "")
    if [[ "$REDIRECT_URL" == https://* ]]; then
        echo "✓ HTTP redirects to HTTPS"
    else
        echo "⚠ HTTP accessible but may not redirect to HTTPS"
    fi
else
    echo "⚠ Could not verify redirect (HTTP code: $HTTP_RESPONSE)"
fi
echo ""

# Test 4: Check SSL certificate
echo "Test 4: SSL Certificate Validation"
echo "----------------------------------------"
if command -v openssl >/dev/null 2>&1; then
    CERT_INFO=$(echo | openssl s_client -servername "$DOMAIN" -connect "$DOMAIN:443" 2>/dev/null | openssl x509 -noout -dates -subject -issuer 2>/dev/null || echo "")
    
    if [ -n "$CERT_INFO" ]; then
        echo "✓ SSL certificate is valid"
        echo ""
        echo "$CERT_INFO"
        echo ""
        
        # Check expiration
        EXPIRY_DATE=$(echo "$CERT_INFO" | grep "notAfter" | cut -d= -f2)
        EXPIRY_EPOCH=$(date -d "$EXPIRY_DATE" +%s 2>/dev/null || date -j -f "%b %d %T %Y %Z" "$EXPIRY_DATE" +%s 2>/dev/null || echo "0")
        CURRENT_EPOCH=$(date +%s)
        DAYS_UNTIL_EXPIRY=$(( ($EXPIRY_EPOCH - $CURRENT_EPOCH) / 86400 ))
        
        if [ "$DAYS_UNTIL_EXPIRY" -gt 30 ]; then
            echo "✓ Certificate expires in $DAYS_UNTIL_EXPIRY days"
        elif [ "$DAYS_UNTIL_EXPIRY" -gt 0 ]; then
            echo "⚠ Certificate expires in $DAYS_UNTIL_EXPIRY days - renewal recommended"
        else
            echo "✗ Certificate has expired!"
        fi
    else
        echo "✗ Could not retrieve SSL certificate"
    fi
else
    echo "⚠ OpenSSL not found, skipping certificate validation"
fi
echo ""

# Test 5: Check SSL protocols
echo "Test 5: SSL/TLS Protocol Support"
echo "----------------------------------------"
if command -v openssl >/dev/null 2>&1; then
    # Test TLS 1.2
    if echo | openssl s_client -tls1_2 -connect "$DOMAIN:443" 2>/dev/null | grep -q "Protocol.*TLSv1.2"; then
        echo "✓ TLS 1.2 supported"
    else
        echo "✗ TLS 1.2 not supported"
    fi
    
    # Test TLS 1.3
    if echo | openssl s_client -tls1_3 -connect "$DOMAIN:443" 2>/dev/null | grep -q "Protocol.*TLSv1.3"; then
        echo "✓ TLS 1.3 supported"
    else
        echo "⚠ TLS 1.3 not supported (optional but recommended)"
    fi
    
    # Test TLS 1.1 (should be disabled)
    if echo | openssl s_client -tls1_1 -connect "$DOMAIN:443" 2>/dev/null | grep -q "Protocol.*TLSv1.1"; then
        echo "⚠ TLS 1.1 supported (should be disabled for security)"
    else
        echo "✓ TLS 1.1 disabled (secure)"
    fi
    
    # Test TLS 1.0 (should be disabled)
    if echo | openssl s_client -tls1 -connect "$DOMAIN:443" 2>/dev/null | grep -q "Protocol.*TLSv1"; then
        echo "⚠ TLS 1.0 supported (should be disabled for security)"
    else
        echo "✓ TLS 1.0 disabled (secure)"
    fi
else
    echo "⚠ OpenSSL not found, skipping protocol tests"
fi
echo ""

# Test 6: Check security headers
echo "Test 6: Security Headers"
echo "----------------------------------------"
if command -v curl >/dev/null 2>&1; then
    HEADERS=$(curl -s -I "https://$DOMAIN" 2>/dev/null || echo "")
    
    if echo "$HEADERS" | grep -qi "Strict-Transport-Security"; then
        echo "✓ HSTS header present"
    else
        echo "✗ HSTS header missing"
    fi
    
    if echo "$HEADERS" | grep -qi "X-Frame-Options"; then
        echo "✓ X-Frame-Options header present"
    else
        echo "✗ X-Frame-Options header missing"
    fi
    
    if echo "$HEADERS" | grep -qi "X-Content-Type-Options"; then
        echo "✓ X-Content-Type-Options header present"
    else
        echo "✗ X-Content-Type-Options header missing"
    fi
    
    if echo "$HEADERS" | grep -qi "Content-Security-Policy"; then
        echo "✓ Content-Security-Policy header present"
    else
        echo "⚠ Content-Security-Policy header missing (recommended)"
    fi
else
    echo "⚠ curl not found, skipping header tests"
fi
echo ""

# Test 7: SSL Labs rating (optional, requires internet)
echo "Test 7: SSL Labs Rating"
echo "----------------------------------------"
echo "For a comprehensive SSL test, visit:"
echo "  https://www.ssllabs.com/ssltest/analyze.html?d=$DOMAIN"
echo ""
echo "Target rating: A or A+"
echo ""

echo "=========================================="
echo "SSL Test Complete"
echo "=========================================="
echo ""
echo "Summary:"
echo "- Ensure all critical tests (✓) pass"
echo "- Address any failures (✗)"
echo "- Consider fixing warnings (⚠) for better security"
echo ""
