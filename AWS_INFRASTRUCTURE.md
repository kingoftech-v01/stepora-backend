# Stepora — AWS Infrastructure Documentation

## Overview

Stepora runs on AWS in the **eu-west-3 (Paris)** region. The architecture is:

```
                    ┌─────────────────────────────────────┐
                    │            Cloudflare DNS            │
                    │  stepora.app → CloudFront (frontend) │
                    │  api.stepora.app → ALB (backend API) │
                    │  stepora.net → ALB (site vitrine)    │
                    └──────────┬──────────┬───────────────┘
                               │          │
                    ┌──────────▼──┐  ┌────▼──────────────┐
                    │ CloudFront  │  │   ALB (HTTPS)      │
                    │ EAG7EHOMSZ  │  │ stepora-alb        │
                    │ stepora.app │  │ Host routing:       │
                    └──────┬──────┘  │ api.* → backend TG  │
                           │         │ stepora.net → site TG│
                    ┌──────▼──────┐  └──┬──────────┬──────┘
                    │     S3      │     │          │
                    │ stepora-    │  ┌──▼───┐  ┌──▼───┐
                    │ frontend-eu │  │ ECS  │  │ ECS  │
                    │ (React SPA) │  │Backend│  │ Site │
                    └─────────────┘  └──┬───┘  └──────┘
                                        │
                              ┌─────────┼─────────┐
                              │         │         │
                         ┌────▼───┐ ┌───▼───┐ ┌───▼──┐
                         │  RDS   │ │ Redis │ │  S3  │
                         │ PG 15  │ │ Cache │ │Media │
                         └────────┘ └───────┘ └──────┘
```

## Account & Region
- **AWS Account**: 987409845802
- **Region**: eu-west-3 (Paris)
- **Free Tier**: Account is on free tier plan

## Domains & DNS (Cloudflare)
| Domain | Type | Target | Purpose |
|--------|------|--------|---------|
| `stepora.app` | CNAME | dw2kyjlud5597.cloudfront.net | Frontend SPA |
| `www.stepora.app` | CNAME | stepora.app | WWW redirect |
| `api.stepora.app` | CNAME | stepora-alb-*.elb.amazonaws.com | Backend API |
| `stepora.net` | CNAME | stepora-alb-*.elb.amazonaws.com | Site vitrine |
| `www.stepora.net` | CNAME | stepora.net | WWW redirect |

**Cloudflare zones**: stepora.app (`9ffc66c3756186d8188a3b90d3ece76f`), stepora.net (`1408f2944265cd6800a196f6f851331f`)

**Important**: All DNS records use "DNS only" (grey cloud), NOT Cloudflare proxy. SSL is handled by AWS (ACM + CloudFront/ALB).

## VPC & Networking

### VPC: `vpc-07d8842dc93e6d3c2` (10.0.0.0/16)

| Subnet | CIDR | AZ | Type | Resources |
|--------|------|----|------|-----------|
| subnet-0e09bc0921f511916 | 10.0.1.0/24 | eu-west-3a | Public | ALB, NAT Gateway |
| subnet-0965c1ff7ce982569 | 10.0.2.0/24 | eu-west-3b | Public | ALB |
| subnet-06432f3e4d876ab42 | 10.0.10.0/24 | eu-west-3a | Private | ECS, RDS, Redis |
| subnet-07af1bd3ed529d510 | 10.0.11.0/24 | eu-west-3b | Private | ECS, RDS, Redis |

**Routing**:
- Public subnets → Internet Gateway (`igw-09e71644388e9a4e3`)
- Private subnets → NAT Gateway (`nat-033035af45dbed5eb`) → Internet (for ECR image pull, etc.)

### Security Groups

| SG | ID | Inbound Rules | Purpose |
|----|-----|--------------|---------|
| stepora-alb-sg | sg-0d80517a3b0338400 | 80, 443 from 0.0.0.0/0 | ALB public access |
| stepora-ecs-sg | sg-0f78df811c5e914ac | 8000 from ALB SG | ECS tasks (only ALB can reach) |
| stepora-rds-sg | sg-05121b2783cd267ac | 5432 from ECS SG | RDS (only ECS can reach) |
| stepora-redis-sg | sg-042e53ce5aaa714ed | 6379 from ECS SG | Redis (only ECS can reach) |

**Security model**: Internet → ALB → ECS → RDS/Redis. Nothing is publicly accessible except the ALB.

## Application Load Balancer

- **Name**: stepora-alb
- **DNS**: stepora-alb-1889641835.eu-west-3.elb.amazonaws.com
- **Subnets**: Both public subnets (for HA)

### Listeners
| Port | Protocol | Action |
|------|----------|--------|
| 80 | HTTP | Redirect to HTTPS (301) |
| 443 | HTTPS | Forward based on host rules |

### HTTPS Host-Based Routing
| Priority | Host | Target Group | Purpose |
|----------|------|-------------|---------|
| 10 | stepora.net, www.stepora.net | stepora-site-tg | Site vitrine |
| Default | * (api.stepora.app) | stepora-backend-tg | Backend API |

### SSL Certificates (ACM)
| Domain | Region | ARN | Status |
|--------|--------|-----|--------|
| stepora.app + *.stepora.app | eu-west-3 | arn:aws:acm:eu-west-3:...:certificate/90581ad3-... | ISSUED |
| stepora.app + *.stepora.app | us-east-1 | arn:aws:acm:us-east-1:...:certificate/a9c9123e-... | ISSUED |
| stepora.net + *.stepora.net | us-east-1 | arn:aws:acm:us-east-1:...:certificate/8266ab99-... | ISSUED |
| stepora.net + *.stepora.net | eu-west-3 | arn:aws:acm:eu-west-3:...:certificate/bb5f97df-... | ISSUED |

Certificates in **us-east-1** are for CloudFront (requires us-east-1). Certificates in **eu-west-3** are for ALB.

## ECS (Elastic Container Service)

### Cluster: `stepora` (Fargate)

| Service | Task Definition | CPU | Memory | Tasks | Image |
|---------|----------------|-----|--------|-------|-------|
| stepora-backend | stepora-backend:1 | 256 | 512 MB | 1 | stepora/backend:latest |
| stepora-site | stepora-site:1 | 256 | 512 MB | 1 | stepora/site:latest |

Both services run in **private subnets** with the ECS security group. They can only be reached through the ALB.

### Backend Task Definition
- **Image**: 987409845802.dkr.ecr.eu-west-3.amazonaws.com/stepora/backend:latest
- **Port**: 8000 (gunicorn, 2 workers + 2 threads)
- **Health check**: `curl -f http://localhost:8000/health/liveness/`
- **Health check grace period**: 120s (allows time for migrations on startup)
- **Startup**: `entrypoint.sh` runs `migrate --noinput` then starts gunicorn
- **Environment**: DJANGO_SETTINGS_MODULE, ALLOWED_HOSTS=*, CORS_ALLOWED_ORIGINS, AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME
- **Secrets** (from Secrets Manager `stepora/backend-env`): DJANGO_SECRET_KEY, FIELD_ENCRYPTION_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, REDIS_URL

### Site Vitrine Task Definition
- **Image**: 987409845802.dkr.ecr.eu-west-3.amazonaws.com/stepora/site:latest
- **Port**: 8000 (gunicorn)
- **Health check**: `curl -f http://localhost:8000/`
- **Environment**: DJANGO_SETTINGS_MODULE, ALLOWED_HOSTS=*, WAGTAILADMIN_BASE_URL, STEPORA_API_URL, STEPORA_APP_URL
- **Secrets** (from Secrets Manager `stepora/site-env`): DJANGO_SECRET_KEY

## ECR (Container Registry)

| Repository | URI | Lifecycle |
|------------|-----|-----------|
| stepora/backend | 987409845802.dkr.ecr.eu-west-3.amazonaws.com/stepora/backend | Keep last 10 images |
| stepora/site | 987409845802.dkr.ecr.eu-west-3.amazonaws.com/stepora/site | Keep last 10 images |

## Database (RDS)

- **Instance**: stepora-db
- **Engine**: PostgreSQL 15
- **Class**: db.t3.micro (free tier)
- **Storage**: 20 GB gp3
- **Endpoint**: `stepora-db.c94aou6wywvf.eu-west-3.rds.amazonaws.com:5432`
- **Database**: stepora
- **Username**: stepora_admin
- **Backup**: 1 day retention (free tier limit)
- **Publicly accessible**: No (private subnets only)

## Cache (ElastiCache)

- **Cluster**: stepora-redis
- **Engine**: Redis
- **Node type**: cache.t3.micro (free tier)
- **Endpoint**: `stepora-redis.jywi3u.0001.euw3.cache.amazonaws.com:6379`
- **Used for**: Django sessions, Celery broker, cache backend

## S3 Buckets

| Bucket | Purpose | Public | Versioning |
|--------|---------|--------|------------|
| stepora-frontend-eu | Frontend SPA (React) | No (CloudFront OAC) | Yes |
| stepora-media-eu | User uploads (images, etc.) | No | No |

## CloudFront

- **Distribution**: EAG7EHOMSZ47W
- **Domain**: dw2kyjlud5597.cloudfront.net
- **Custom domains**: stepora.app, www.stepora.app
- **Origin**: S3 bucket (stepora-frontend-eu) via OAC
- **Default root**: index.html
- **Error pages**: 403 → /index.html, 404 → /index.html (SPA routing)
- **SSL**: ACM certificate (us-east-1), TLSv1.2_2021, SNI
- **Price class**: PriceClass_100 (cheapest — US, Canada, Europe)

## IAM

### Roles
| Role | Trust | Policies | Purpose |
|------|-------|----------|---------|
| stepora-ecs-execution-role | ecs-tasks.amazonaws.com | AmazonECSTaskExecutionRolePolicy + stepora-secrets-access | Pull images, read secrets, write logs |
| stepora-ecs-task-role | ecs-tasks.amazonaws.com | stepora-task-permissions (S3 + SES) | App runtime permissions |

### CI/CD
| User | Access Key | Policy | Purpose |
|------|------------|--------|---------|
| stepora-ci-deploy | [STORED IN GITHUB SECRETS] | stepora-ci-deploy-policy | GitHub Actions deploy |

**stepora-ci-deploy-policy** allows: ECR push, ECS update, S3 sync, CloudFront invalidate, IAM PassRole for ECS roles.

## Secrets Manager

- **Secret**: `stepora/backend-env`
  - **Keys**: DJANGO_SECRET_KEY, FIELD_ENCRYPTION_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, REDIS_URL
- **Secret**: `stepora/site-env`
  - **Keys**: DJANGO_SECRET_KEY

**Important**: No secrets are stored in `.env` files or committed code. All sensitive values are in AWS Secrets Manager (runtime) and GitHub Secrets (CI/CD).

## CloudWatch Logs

| Log Group | Retention | Source |
|-----------|-----------|--------|
| /ecs/stepora-backend | 30 days | Backend ECS tasks |
| /ecs/stepora-site | 30 days | Site vitrine ECS tasks |

## Branch Architecture & CI/CD

```
feature/xxx ──PR──► development (preprod) ──merge──► main (production)
                         │                              │
                    CI only (lint/test)         CI + CD (deploy to AWS)
                    VPS: *.jhpetitfrere.com     AWS: stepora.app / stepora.net / api.stepora.app
```

### Rules
- **Feature branches** → merge into `development` via Pull Request
- **development** → CI runs lint/tests, NO deployment. Preprod is the local VPS at `*.jhpetitfrere.com`
- **main** → CI runs lint/tests, then CD builds Docker image, pushes to ECR, deploys to ECS
- Both `main` and `development` must stay on the same latest commit (merge development→main to deploy)

### Deploy Guards
All deploy/build-and-push jobs have: `if: github.ref == 'refs/heads/main' && github.event_name == 'push'`

## CI/CD (GitHub Actions)

GitHub Secrets are configured on all 3 repos:

### Backend (`kingoftech-v01/stepora-backend`)
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_ACCOUNT_ID
- ECR_REPOSITORY (stepora/backend), ECS_CLUSTER (stepora), ECS_SERVICE (stepora-backend)

### Frontend (`kingoftech-v01/stepora-frontend`)
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
- S3_BUCKET_FRONTEND (stepora-frontend-eu), CLOUDFRONT_DISTRIBUTION_ID_FRONTEND (EAG7EHOMSZ47W)

### Site Vitrine (`kingoftech-v01/stepora-site`)
- AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, AWS_ACCOUNT_ID
- ECR_REPOSITORY (stepora/site), ECS_CLUSTER (stepora), ECS_SERVICE (stepora-site)

## Cost Estimate (Free Tier)

Most resources are free tier eligible:
- **RDS**: db.t3.micro — 750 hrs/month free for 12 months
- **ElastiCache**: cache.t3.micro — 750 hrs/month free for 12 months
- **ECS Fargate**: ~$10-15/month (256 CPU, 512 MB, 2 services)
- **ALB**: ~$16/month (fixed cost)
- **NAT Gateway**: ~$32/month (this is the most expensive part)
- **S3**: Negligible (~$0.01/month)
- **CloudFront**: 1 TB free, then $0.085/GB
- **Data transfer**: 100 GB free

**Estimated monthly cost**: ~$60-70/month (NAT GW is the largest cost)

**Cost optimization**: Could reduce NAT GW cost by giving ECS tasks public IPs (but less secure).
