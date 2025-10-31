# MSS Cloud Run Deployment Runbook

## Quick Reference

**Service Name:** `mss-api`  
**Region:** `us-central1`  
**Project:** `mss-production` (or your project ID)

## Common Commands

### View Service Status
```bash
gcloud run services describe mss-api --region us-central1
```

### View Logs
```bash
gcloud run services logs read mss-api --region us-central1 --limit=50
```

### Update Environment Variables
```bash
gcloud run services update mss-api \
  --region us-central1 \
  --update-env-vars "KEY=VALUE"
```

### Update Secrets
```bash
gcloud run services update mss-api \
  --region us-central1 \
  --update-secrets "SECRET_NAME=secret-name:latest"
```

### Scale Service
```bash
gcloud run services update mss-api \
  --region us-central1 \
  --min-instances 1 \
  --max-instances 10 \
  --cpu 2 \
  --memory 2Gi
```

### Rollback to Previous Revision
```bash
# List revisions
gcloud run revisions list --service mss-api --region us-central1

# Rollback
gcloud run services update-traffic mss-api \
  --to-revisions REVISION_NAME=100 \
  --region us-central1
```

## Rollback Procedure

1. **Identify failed revision:**
   ```bash
   gcloud run revisions list --service mss-api --region us-central1
   ```

2. **Find last working revision:** Look for revision with 100% traffic that was working

3. **Rollback:**
   ```bash
   gcloud run services update-traffic mss-api \
     --to-revisions LAST_WORKING_REVISION=100 \
     --region us-central1
   ```

4. **Verify:**
   ```bash
   SERVICE_URL=$(gcloud run services describe mss-api --region us-central1 --format 'value(status.url)')
   curl "$SERVICE_URL/healthz"
   ```

## Emergency Procedures

### Service Down
1. Check Cloud Run status: `gcloud run services describe mss-api --region us-central1`
2. Check logs: `gcloud run services logs read mss-api --region us-central1 --limit=100`
3. Rollback if recent deploy: Use rollback procedure above
4. Check quotas: `gcloud compute project-info describe --project mss-production`

### High Error Rate
1. Check logs for error patterns
2. Check Secret Manager secrets are accessible
3. Verify Cloud Storage bucket permissions
4. Check service account has required roles

### Out of Memory
1. Increase memory: `gcloud run services update mss-api --region us-central1 --memory 4Gi`
2. Check for memory leaks in logs
3. Consider reducing workers/threads

### Database Issues
- If using SQLite: Data is ephemeral, restart may clear issues
- If using Cloud SQL: Check connection string and proxy status

## Monitoring

### Set Up Alerts
1. Go to Cloud Console → Cloud Run → mss-api → Alerts
2. Create alerts for:
   - Error rate > 1%
   - Request latency > 5s
   - Memory usage > 80%
   - CPU usage > 80%

### Health Checks
- Endpoint: `/healthz` (must return 200 OK)
- Endpoint: `/health` (detailed status)
- Check frequency: Cloud Run default (every 60s)

## Maintenance Windows

### Update Secrets
```bash
# Update secret value
echo -n "new-value" | gcloud secrets versions add secret-name --data-file=-

# Update service to use new version
gcloud run services update mss-api \
  --region us-central1 \
  --update-secrets "SECRET_NAME=secret-name:latest"
```

### Update Service Configuration
```bash
# Edit service YAML
gcloud run services describe mss-api --region us-central1 --format export > service.yaml

# Edit service.yaml, then apply
gcloud run services replace service.yaml --region us-central1
```

## Troubleshooting Checklist

- [ ] Service is running: `gcloud run services describe mss-api --region us-central1`
- [ ] Health endpoint responds: `curl https://SERVICE_URL/healthz`
- [ ] Logs show no errors: `gcloud run services logs read mss-api --region us-central1`
- [ ] Secrets are accessible: Check IAM permissions
- [ ] Cloud Storage bucket exists and is accessible
- [ ] Service account has required roles
- [ ] No quota limits exceeded
- [ ] Environment variables are set correctly

