# Secret Management Guidelines

## Overview

This document provides comprehensive guidelines for managing secrets and sensitive configuration in the Proactive Accountability Assistant application. Proper secret management is critical for security in production environments.

## Table of Contents

1. [General Principles](#general-principles)
2. [Secret Types](#secret-types)
3. [Generating Secure Secrets](#generating-secure-secrets)
4. [Storage and Access](#storage-and-access)
5. [Environment-Specific Configuration](#environment-specific-configuration)
6. [Rotation and Updates](#rotation-and-updates)
7. [Emergency Procedures](#emergency-procedures)
8. [Compliance and Auditing](#compliance-and-auditing)

## General Principles

### Never Commit Secrets to Version Control

**CRITICAL**: Never commit secrets, API keys, passwords, or tokens to Git repositories.

- Add `.env.production` to `.gitignore`
- Use `.env.example` files with placeholder values
- Review commits before pushing to ensure no secrets are included
- Use tools like `git-secrets` or `truffleHog` to scan for accidentally committed secrets

### Principle of Least Privilege

- Grant access to secrets only to services and people who need them
- Use separate credentials for different environments (dev, staging, production)
- Rotate credentials when team members leave or roles change

### Defense in Depth

- Use multiple layers of security (encryption at rest, in transit, access controls)
- Assume any single layer may be compromised
- Monitor and audit secret access

## Secret Types

### 1. Database Credentials

**What**: PostgreSQL username and password

**Risk Level**: CRITICAL - Full access to all application data

**Requirements**:
- Minimum 32 characters
- Mix of uppercase, lowercase, numbers, and special characters
- Unique per environment
- Never reuse passwords

**Generate with**:
```bash
openssl rand -base64 32
```

### 2. JWT Secret Key

**What**: Key used to sign and verify JWT authentication tokens

**Risk Level**: CRITICAL - Compromise allows impersonation of any user

**Requirements**:
- Minimum 64 characters (hex) or 32 bytes
- Cryptographically random
- Never reuse across environments
- Rotation requires re-authentication of all users

**Generate with**:
```bash
openssl rand -hex 32
```

### 3. Encryption Key (Fernet)

**What**: Key used to encrypt sensitive data at rest

**Risk Level**: CRITICAL - Compromise exposes encrypted user data

**Requirements**:
- Must be a valid Fernet key (44 characters, base64-encoded)
- Cryptographically random
- Backup securely before rotation (needed to decrypt existing data)

**Generate with**:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. API Keys (Anthropic)

**What**: Third-party service authentication

**Risk Level**: HIGH - Compromise leads to unauthorized API usage and costs

**Requirements**:
- Obtain from official provider dashboard
- Monitor usage for anomalies
- Set usage limits where possible
- Rotate if compromised

**Obtain from**: https://console.anthropic.com/

### 5. Discord Credentials

**What**: Bot token, OAuth client ID and secret

**Risk Level**: HIGH - Compromise allows bot impersonation and user data access

**Requirements**:
- Bot token: Keep absolutely secret
- Client secret: Treat as highly sensitive
- Client ID: Less sensitive but don't expose unnecessarily
- Regenerate immediately if compromised

**Obtain from**: https://discord.com/developers/applications

### 6. Webhook Secrets

**What**: Shared secrets for validating incoming webhooks

**Risk Level**: MEDIUM - Compromise allows spoofed webhook requests

**Requirements**:
- Minimum 32 characters
- Cryptographically random
- Rotate periodically

**Generate with**:
```bash
openssl rand -hex 32
```

## Generating Secure Secrets

### Using OpenSSL (Recommended)

OpenSSL is available on most systems and provides cryptographically secure random data.

```bash
# Generate 32-byte hex string (64 characters)
openssl rand -hex 32

# Generate 32-byte base64 string
openssl rand -base64 32

# Generate 64-byte hex string (128 characters)
openssl rand -hex 64
```

### Using Python

```python
# Generate hex string
import secrets
print(secrets.token_hex(32))  # 64 character hex string

# Generate URL-safe string
print(secrets.token_urlsafe(32))  # ~43 character URL-safe string

# Generate Fernet key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

### Using Node.js

```javascript
// Generate hex string
const crypto = require('crypto');
console.log(crypto.randomBytes(32).toString('hex'));

// Generate base64 string
console.log(crypto.randomBytes(32).toString('base64'));
```

### What NOT to Use

❌ **DO NOT USE**:
- Dictionary words or phrases
- Personal information (names, dates, etc.)
- Sequential or predictable patterns
- Short strings (< 16 characters)
- `Math.random()` or similar non-cryptographic RNGs
- Reused passwords from other services

## Storage and Access

### Local Development

**File**: `.env` in project root

**Security**:
- Listed in `.gitignore`
- Use development-specific values (never production secrets)
- Can use weaker secrets for convenience

**Access**: All developers on the project

### Production Deployment

**File**: `.env.production` on production server

**Security**:
- Never commit to version control
- Restrict file permissions: `chmod 600 .env.production`
- Store in secure location on server
- Backup encrypted to secure location

**Access**: Only system administrators and deployment automation

### Recommended Secret Management Solutions

For production deployments, consider using dedicated secret management tools:

#### 1. HashiCorp Vault

**Pros**:
- Industry standard
- Dynamic secrets
- Audit logging
- Fine-grained access control

**Cons**:
- Complex setup
- Additional infrastructure

#### 2. AWS Secrets Manager

**Pros**:
- Managed service
- Automatic rotation
- Integration with AWS services

**Cons**:
- AWS-specific
- Additional cost

#### 3. Docker Secrets (Docker Swarm)

**Pros**:
- Built into Docker
- Encrypted at rest and in transit
- Simple for Docker-based deployments

**Cons**:
- Requires Docker Swarm mode
- Limited to Docker environments

#### 4. Environment Variables (Current Approach)

**Pros**:
- Simple
- No additional infrastructure
- Works everywhere

**Cons**:
- No automatic rotation
- Manual management
- Visible in process listings

**Recommendation**: Start with environment variables (current approach) for simplicity. Migrate to Vault or cloud provider secrets manager as the application scales.

## Environment-Specific Configuration

### Development Environment

**Purpose**: Local development and testing

**Security Level**: Low (convenience prioritized)

**Characteristics**:
- Can use simple, memorable secrets
- Shared among all developers
- Committed to `.env.example` as examples
- Uses `localhost` URLs
- Debug mode enabled

**Example**:
```bash
ENVIRONMENT=development
DEBUG=True
JWT_SECRET_KEY=dev-secret-key-not-for-production
DATABASE_URL=postgresql://dev:dev@localhost:5432/dev_db
```

### Staging Environment

**Purpose**: Pre-production testing

**Security Level**: Medium (production-like but isolated)

**Characteristics**:
- Production-strength secrets
- Separate from production
- Limited access
- Production-like configuration
- May use test API keys with limits

**Example**:
```bash
ENVIRONMENT=staging
DEBUG=False
JWT_SECRET_KEY=<strong-random-secret-different-from-prod>
DATABASE_URL=postgresql://staging_user:strong_pass@staging-db:5432/staging_db
```

### Production Environment

**Purpose**: Live application serving real users

**Security Level**: CRITICAL (maximum security)

**Characteristics**:
- Strongest possible secrets
- Strictly controlled access
- Regular rotation schedule
- Comprehensive monitoring
- Production API keys

**Example**:
```bash
ENVIRONMENT=production
DEBUG=False
JWT_SECRET_KEY=<64-char-cryptographically-random-hex>
DATABASE_URL=postgresql://prod_user:32-char-random@prod-db:5432/prod_db
```

## Rotation and Updates

### When to Rotate Secrets

**Immediately**:
- Secret is compromised or suspected compromise
- Team member with access leaves
- Service breach reported by provider
- Secret accidentally committed to version control
- Secret exposed in logs or error messages

**Regularly (Scheduled)**:
- Database passwords: Every 90 days
- JWT secret keys: Every 180 days (requires user re-authentication)
- API keys: Per provider recommendations
- Webhook secrets: Every 90 days

**On Demand**:
- Before major security audits
- After security incidents
- When upgrading security posture

### Rotation Procedures

#### Database Password Rotation

1. Create new database user with new password
2. Grant same permissions as old user
3. Update `.env.production` with new credentials
4. Restart application services
5. Verify application works correctly
6. Remove old database user
7. Update backup scripts with new credentials

#### JWT Secret Key Rotation

⚠️ **WARNING**: Rotating JWT secret invalidates all existing user sessions

1. Schedule maintenance window
2. Notify users of upcoming re-authentication requirement
3. Generate new JWT secret
4. Update `.env.production`
5. Restart backend services
6. All users must log in again
7. Monitor for authentication issues

#### Encryption Key Rotation

⚠️ **WARNING**: Complex process - requires re-encrypting all data

1. **DO NOT** delete old encryption key yet
2. Generate new encryption key
3. Add new key to configuration as `ENCRYPTION_KEY_NEW`
4. Run migration script to re-encrypt data with new key
5. Verify all data re-encrypted successfully
6. Update `ENCRYPTION_KEY` to new value
7. Remove `ENCRYPTION_KEY_NEW`
8. Securely backup old key for 90 days (in case of issues)
9. Securely destroy old key after retention period

#### API Key Rotation

1. Generate new API key from provider dashboard
2. Update `.env.production` with new key
3. Restart affected services
4. Verify functionality
5. Revoke old API key from provider dashboard
6. Monitor for any services still using old key

### Rotation Checklist

Before rotating any secret:

- [ ] Identify all services using the secret
- [ ] Plan rotation sequence to minimize downtime
- [ ] Backup current configuration
- [ ] Test rotation procedure in staging
- [ ] Schedule maintenance window if needed
- [ ] Prepare rollback plan
- [ ] Update documentation
- [ ] Notify relevant team members

After rotating:

- [ ] Verify all services work correctly
- [ ] Check logs for authentication errors
- [ ] Update backup/restore procedures
- [ ] Document rotation in change log
- [ ] Securely destroy old secret
- [ ] Update secret inventory

## Emergency Procedures

### Secret Compromise Response

If a secret is compromised or suspected to be compromised:

#### Immediate Actions (Within 1 Hour)

1. **Assess Impact**
   - Identify which secret was compromised
   - Determine potential access granted by secret
   - Check logs for unauthorized access

2. **Contain**
   - Rotate compromised secret immediately
   - Revoke API keys from provider dashboards
   - Block suspicious IP addresses
   - Enable additional monitoring

3. **Notify**
   - Alert security team
   - Notify affected users if user data accessed
   - Report to relevant authorities if required

#### Short-Term Actions (Within 24 Hours)

4. **Investigate**
   - Review access logs
   - Identify scope of compromise
   - Determine how secret was exposed
   - Document timeline of events

5. **Remediate**
   - Fix vulnerability that led to exposure
   - Rotate related secrets as precaution
   - Update security procedures
   - Implement additional controls

#### Long-Term Actions (Within 1 Week)

6. **Review and Improve**
   - Conduct post-incident review
   - Update security policies
   - Provide team training
   - Implement preventive measures
   - Update incident response procedures

### Accidental Commit to Git

If secrets are accidentally committed to Git:

1. **DO NOT** just delete the file and commit again (secret remains in history)
2. Immediately rotate the compromised secrets
3. Remove secret from Git history:
   ```bash
   # Using git filter-branch (for small repos)
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .env.production" \
     --prune-empty --tag-name-filter cat -- --all
   
   # Or using BFG Repo-Cleaner (recommended for large repos)
   bfg --delete-files .env.production
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   ```
4. Force push to remote (coordinate with team):
   ```bash
   git push origin --force --all
   git push origin --force --tags
   ```
5. All team members must re-clone the repository
6. If repository is public, assume secret is compromised

## Compliance and Auditing

### Secret Inventory

Maintain an inventory of all secrets (not the values, just metadata):

| Secret Name | Type | Last Rotated | Rotation Schedule | Owner | Access Level |
|-------------|------|--------------|-------------------|-------|--------------|
| POSTGRES_PASSWORD | Database | 2024-01-15 | 90 days | DevOps | Critical |
| JWT_SECRET_KEY | Auth | 2024-02-01 | 180 days | Backend | Critical |
| ANTHROPIC_API_KEY | API | 2024-01-20 | As needed | Backend | High |

### Audit Logging

Log all secret-related activities:

- Secret rotation events
- Access to secret storage
- Failed authentication attempts
- API key usage patterns
- Configuration changes

### Regular Reviews

**Monthly**:
- Review access logs for anomalies
- Check for expiring secrets
- Verify backup procedures

**Quarterly**:
- Audit secret inventory
- Review and update rotation schedules
- Test secret rotation procedures
- Review access permissions

**Annually**:
- Comprehensive security audit
- Update secret management policies
- Review and update this documentation
- Team training on secret management

### Compliance Requirements

Depending on your jurisdiction and industry, you may need to comply with:

- **GDPR**: Encryption of personal data, access controls
- **HIPAA**: Encryption, audit trails, access controls
- **PCI DSS**: Strong cryptography, key management
- **SOC 2**: Access controls, encryption, monitoring

Consult with legal and compliance teams to ensure secret management meets all requirements.

## Quick Reference

### Common Commands

```bash
# Generate database password
openssl rand -base64 32

# Generate JWT secret
openssl rand -hex 32

# Generate Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Validate environment configuration
./scripts/validate-env.sh .env.production

# Check file permissions
ls -la .env.production

# Set secure file permissions
chmod 600 .env.production

# View environment variables (be careful!)
cat .env.production

# Search for accidentally committed secrets
git log -p | grep -i "password\|secret\|key"
```

### Security Checklist

Before deploying to production:

- [ ] All secrets generated with cryptographically secure methods
- [ ] No default or placeholder values remain
- [ ] `.env.production` not committed to Git
- [ ] File permissions set to 600 (owner read/write only)
- [ ] Secrets meet minimum length requirements
- [ ] Different secrets used for each environment
- [ ] Backup of secrets stored securely offline
- [ ] Secret rotation schedule documented
- [ ] Team trained on secret management procedures
- [ ] Incident response plan in place

## Additional Resources

- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [NIST Guidelines for Password Management](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [CIS Controls for Secret Management](https://www.cisecurity.org/controls)
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)

## Support

For questions or concerns about secret management:

1. Review this documentation
2. Consult with security team
3. Refer to incident response procedures if compromise suspected

---

**Last Updated**: 2024-01-15  
**Document Owner**: DevOps/Security Team  
**Review Schedule**: Quarterly
