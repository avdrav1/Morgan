# Production Deployment Checklist

Use this checklist to ensure a smooth production deployment.

## Pre-Deployment

### Server Setup
- [ ] Server provisioned (minimum 2 CPU, 4GB RAM, 50GB disk)
- [ ] Ubuntu 22.04 LTS (or similar) installed
- [ ] Server accessible via SSH
- [ ] Public IP address assigned
- [ ] Domain name configured (if using SSL)

### Software Installation
- [ ] Docker installed (version 20.10+)
- [ ] Docker Compose installed (version 2.0+)
- [ ] Git installed
- [ ] User added to docker group: `sudo usermod -aG docker $USER`
- [ ] Logged out and back in (for docker group to take effect)

### Firewall Configuration
- [ ] UFW installed: `sudo apt install ufw`
- [ ] Port 22 allowed: `sudo ufw allow 22/tcp`
- [ ] Port 80 allowed: `sudo ufw allow 80/tcp`
- [ ] Port 443 allowed: `sudo ufw allow 443/tcp`
- [ ] Firewall enabled: `sudo ufw enable`
- [ ] Firewall status verified: `sudo ufw status`

### Repository Setup
- [ ] Repository cloned: `git clone <repository-url>`
- [ ] Changed to project directory: `cd accountability-assistant`
- [ ] On correct branch: `git checkout main`
- [ ] Latest code pulled: `git pull origin main`

### Environment Configuration
- [ ] `.env.production` created from template: `cp .env.production.example .env.production`
- [ ] All required variables filled in `.env.production`
- [ ] Secrets generated (see below)
- [ ] URLs updated with actual domain
- [ ] API keys added
- [ ] Discord credentials configured
- [ ] Environment validated: `bash scripts/validate-env.sh .env.production`

### Secret Generation
- [ ] JWT secret generated: `openssl rand -hex 32`
- [ ] Encryption key generated: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Webhook secret generated: `openssl rand -hex 32`
- [ ] Database password generated: `openssl rand -base64 32`
- [ ] All secrets added to `.env.production`
- [ ] `.env.production` NOT committed to git

### DNS Configuration (if using SSL)
- [ ] A record created: `yourdomain.com → <server-ip>`
- [ ] A record created: `www.yourdomain.com → <server-ip>`
- [ ] DNS propagation verified: `nslookup yourdomain.com`
- [ ] Domain resolves to server IP

## Deployment

### Pre-Flight Checks
- [ ] Deployment script executable: `chmod +x deploy.sh`
- [ ] Help displayed correctly: `./deploy.sh --help`
- [ ] Syntax check passed: `bash -n deploy.sh`
- [ ] Sufficient disk space: `df -h` (minimum 5GB free)
- [ ] Docker daemon running: `docker ps`

### Run Deployment
- [ ] Deployment initiated: `./deploy.sh`
- [ ] Prerequisites check passed
- [ ] Environment validation passed
- [ ] Port availability check passed
- [ ] Pre-deployment backup created
- [ ] Docker images built successfully
- [ ] Services started in order
- [ ] Health checks passed
- [ ] API endpoints responding
- [ ] Deployment completed successfully

### Deployment Verification
- [ ] All services running: `docker-compose -f docker-compose.prod.yml ps`
- [ ] No services in "Exit" state
- [ ] Backend health endpoint responding: `curl http://localhost/api/health`
- [ ] Nginx health endpoint responding: `curl http://localhost/health`
- [ ] Logs show no errors: `docker-compose -f docker-compose.prod.yml logs --tail=50`

## Post-Deployment

### SSL Certificate Setup
- [ ] SSL setup script executed: `bash nginx/setup-ssl-prod.sh`
- [ ] Certificates obtained successfully
- [ ] HTTPS working: `curl https://yourdomain.com/health`
- [ ] HTTP redirects to HTTPS
- [ ] Certificate auto-renewal configured

### Backup Configuration
- [ ] Backup cron job configured: `bash scripts/setup-backup-cron.sh`
- [ ] Backup directory exists: `ls -la backups/`
- [ ] Manual backup tested: `bash scripts/backup-database.sh`
- [ ] Backup created successfully
- [ ] Backup restore tested: `bash scripts/restore-database.sh <backup-file>`

### Monitoring Setup
- [ ] Deployment log reviewed: `cat deployment.log`
- [ ] Service logs reviewed: `docker-compose -f docker-compose.prod.yml logs`
- [ ] Resource usage checked: `docker stats`
- [ ] Disk usage checked: `df -h`
- [ ] No critical errors in logs

### Application Testing
- [ ] Frontend accessible: `https://yourdomain.com`
- [ ] Login page loads
- [ ] API documentation accessible: `https://yourdomain.com/api/docs`
- [ ] Discord bot online in Discord server
- [ ] Test user registration works
- [ ] Test user login works
- [ ] Test project creation works
- [ ] Test Discord integration works

### Security Hardening
- [ ] SSH key-based authentication configured
- [ ] Password authentication disabled in SSH
- [ ] Fail2ban installed and configured (optional)
- [ ] Unattended-upgrades configured (optional)
- [ ] Security headers verified in Nginx
- [ ] CORS origins properly configured
- [ ] Rate limiting tested

### Documentation
- [ ] Deployment documented in team wiki/docs
- [ ] Server access credentials stored securely
- [ ] Environment variables documented
- [ ] Backup procedures documented
- [ ] Rollback procedures documented
- [ ] On-call procedures documented

## Ongoing Maintenance

### Daily
- [ ] Check service health: `docker-compose -f docker-compose.prod.yml ps`
- [ ] Review error logs: `docker-compose -f docker-compose.prod.yml logs --tail=100 | grep -i error`
- [ ] Verify backups completed: `ls -lh backups/daily/`
- [ ] Check disk space: `df -h`

### Weekly
- [ ] Review all logs: `docker-compose -f docker-compose.prod.yml logs --tail=500`
- [ ] Check resource usage: `docker stats`
- [ ] Review security logs: `sudo tail -100 /var/log/auth.log`
- [ ] Test backup restoration
- [ ] Check for application updates

### Monthly
- [ ] Update system packages: `sudo apt update && sudo apt upgrade -y`
- [ ] Update Docker images: `docker-compose -f docker-compose.prod.yml pull`
- [ ] Review and rotate logs
- [ ] Test disaster recovery procedures
- [ ] Security audit
- [ ] Performance review

## Rollback Procedures

### If Deployment Fails
- [ ] Automatic rollback initiated by script
- [ ] Services stopped
- [ ] Previous state identified
- [ ] Backup location identified
- [ ] Manual restoration steps followed

### Manual Rollback
- [ ] Rollback initiated: `./deploy.sh --rollback`
- [ ] Services stopped
- [ ] Database restored: `bash scripts/restore-database.sh <backup-file>`
- [ ] Previous code checked out: `git checkout <previous-commit>`
- [ ] Images rebuilt: `docker-compose -f docker-compose.prod.yml build`
- [ ] Services restarted: `docker-compose -f docker-compose.prod.yml up -d`
- [ ] Health verified
- [ ] Issue documented for future reference

## Troubleshooting

### Common Issues Checklist

#### Port Conflicts
- [ ] Identified conflicting process: `sudo lsof -i :80` and `sudo lsof -i :443`
- [ ] Stopped conflicting service
- [ ] Rerun deployment

#### Environment Validation Failures
- [ ] Reviewed validation output
- [ ] Fixed missing/invalid variables
- [ ] Regenerated secrets if needed
- [ ] Revalidated: `bash scripts/validate-env.sh .env.production`

#### Build Failures
- [ ] Checked Docker disk space: `docker system df`
- [ ] Cleaned up if needed: `docker system prune -a`
- [ ] Reviewed build logs
- [ ] Fixed Dockerfile issues
- [ ] Rebuilt with verbose output

#### Health Check Failures
- [ ] Identified failing service
- [ ] Reviewed service logs: `docker-compose -f docker-compose.prod.yml logs <service>`
- [ ] Checked service configuration
- [ ] Restarted service: `docker-compose -f docker-compose.prod.yml restart <service>`
- [ ] Verified health: `docker inspect <container-name>`

#### Database Connection Issues
- [ ] Verified PostgreSQL running: `docker-compose -f docker-compose.prod.yml ps postgres`
- [ ] Checked PostgreSQL logs: `docker-compose -f docker-compose.prod.yml logs postgres`
- [ ] Verified DATABASE_URL matches POSTGRES_* variables
- [ ] Tested connection from backend container

## Emergency Contacts

Document your emergency contacts:

- **System Administrator**: _______________
- **Database Administrator**: _______________
- **DevOps Lead**: _______________
- **On-Call Engineer**: _______________
- **Hosting Provider Support**: _______________

## Important URLs

Document your important URLs:

- **Production URL**: https://_______________
- **API Documentation**: https://_______________/api/docs
- **Monitoring Dashboard**: https://_______________
- **Log Aggregation**: https://_______________
- **Status Page**: https://_______________

## Important Files

Document locations of important files:

- **Environment File**: `.env.production` (NOT in git)
- **Deployment Log**: `deployment.log`
- **Backup Directory**: `backups/`
- **SSL Certificates**: `nginx/ssl/` or `/etc/letsencrypt/`
- **Nginx Logs**: `docker volume inspect accountability-nginx-logs`

## Notes

Use this space for deployment-specific notes:

```
Deployment Date: _______________
Deployed By: _______________
Git Commit: _______________
Issues Encountered: _______________
Resolution: _______________
```

---

**Remember**: Always test in a staging environment before deploying to production!
