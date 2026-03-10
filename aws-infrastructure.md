# Stepora AWS Infrastructure — eu-west-3 (Paris)

## Account
- Account ID: 987409845802
- Region: eu-west-3

## Domains
- stepora.app → frontend app (CloudFront) + api.stepora.app (ALB)
- stepora.net → site vitrine
- DNS managed in Cloudflare

## VPC & Networking
- VPC: vpc-07d8842dc93e6d3c2 (10.0.0.0/16)
- Public Subnet 1 (eu-west-3a): subnet-0e09bc0921f511916 (10.0.1.0/24)
- Public Subnet 2 (eu-west-3b): subnet-0965c1ff7ce982569 (10.0.2.0/24)
- Private Subnet 1 (eu-west-3a): subnet-06432f3e4d876ab42 (10.0.10.0/24)
- Private Subnet 2 (eu-west-3b): subnet-07af1bd3ed529d510 (10.0.11.0/24)
- Internet Gateway: igw-09e71644388e9a4e3
- NAT Gateway: nat-033035af45dbed5eb (EIP: eipalloc-01a0c8714a4311ce4)
- Public Route Table: rtb-05da238252dbbadf1 (0.0.0.0/0 → IGW)
- Private Route Table: rtb-079190e9f92ab21b3 (0.0.0.0/0 → NAT)

## Security Groups
- ALB: sg-0d80517a3b0338400 (inbound 80, 443 from 0.0.0.0/0)
- ECS: sg-0f78df811c5e914ac (inbound 8000 from ALB SG)
- RDS: sg-05121b2783cd267ac (inbound 5432 from ECS SG)
- Redis: sg-042e53ce5aaa714ed (inbound 6379 from ECS SG)

## ECR Repositories
- Backend: 987409845802.dkr.ecr.eu-west-3.amazonaws.com/stepora/backend
- Site: 987409845802.dkr.ecr.eu-west-3.amazonaws.com/stepora/site

## ECS
- Cluster: stepora (arn:aws:ecs:eu-west-3:987409845802:cluster/stepora)

## Load Balancer
- ALB: stepora-alb (arn:aws:elasticloadbalancing:eu-west-3:987409845802:loadbalancer/app/stepora-alb/7da1864666583fe0)
- ALB DNS: stepora-alb-1889641835.eu-west-3.elb.amazonaws.com
- Target Group (backend): arn:aws:elasticloadbalancing:eu-west-3:987409845802:targetgroup/stepora-backend-tg/cb24a012479c1563
- HTTP Listener: arn:aws:elasticloadbalancing:eu-west-3:987409845802:listener/app/stepora-alb/7da1864666583fe0/879b87f7841d4cb2

## RDS
- Instance: stepora-db (db.t3.micro, PostgreSQL 15)
- DB Name: stepora
- Username: stepora_admin
- Password: [STORED IN AWS SECRETS MANAGER — stepora/backend-env]
- Endpoint: stepora-db.c94aou6wywvf.eu-west-3.rds.amazonaws.com:5432

## ElastiCache Redis
- Cluster: stepora-redis (cache.t3.micro)
- Endpoint: stepora-redis.jywi3u.0001.euw3.cache.amazonaws.com:6379

## S3 Buckets
- Frontend: stepora-frontend-eu
- Media: stepora-media-eu

## CloudFront
- Frontend Distribution: EAG7EHOMSZ47W
- Frontend Domain: dw2kyjlud5597.cloudfront.net
- OAC: E1CSCAJUGWEP3S

## IAM
- ECS Execution Role: arn:aws:iam::987409845802:role/stepora-ecs-execution-role
- ECS Task Role: arn:aws:iam::987409845802:role/stepora-ecs-task-role
- CI/CD Deploy Policy: arn:aws:iam::987409845802:policy/stepora-ci-deploy-policy

## SSL Certificates
- stepora.app (eu-west-3): arn:aws:acm:eu-west-3:987409845802:certificate/90581ad3-11fa-4aa4-9692-99681e68a9e8
- stepora.net (us-east-1, for CloudFront): arn:aws:acm:us-east-1:987409845802:certificate/8266ab99-2dfa-4440-88fa-3a68c02ae161
- stepora.app (us-east-1, for CloudFront): arn:aws:acm:us-east-1:987409845802:certificate/a9c9123e-f725-4cc6-a358-3465eac346f1

## Secrets Manager
- Backend env: arn:aws:secretsmanager:eu-west-3:987409845802:secret:stepora/backend-env-5zApQX

## CloudWatch Log Groups
- /ecs/stepora-backend (30 day retention)
- /ecs/stepora-site (30 day retention)

## DNS (Cloudflare) — ALL CONFIGURED
- stepora.app → dw2kyjlud5597.cloudfront.net (CloudFront, frontend)
- www.stepora.app → stepora.app
- api.stepora.app → stepora-alb-1889641835.eu-west-3.elb.amazonaws.com (ALB, backend)
- stepora.net → stepora-alb-1889641835.eu-west-3.elb.amazonaws.com (ALB, site vitrine)
- www.stepora.net → stepora.net
- ACM validation CNAMEs for both domains (certs ISSUED)

## ALB Listeners
- HTTP (80): Redirects to HTTPS (301)
- HTTPS (443): Forwards to stepora-backend-tg, cert: stepora.app

## CI/CD Deploy User
- Username: stepora-ci-deploy
- Access Key: [STORED IN GITHUB SECRETS]
- Policy: stepora-ci-deploy-policy (ECR, ECS, S3, CloudFront)
- GitHub Secrets configured on all 3 repos

## Deployment Status
- Frontend: DEPLOYED to S3 + CloudFront (stepora.app)
- Backend: ECS service created, awaiting first image push
- Site vitrine: Needs ECS task def + service (currently on VPS)

## Remaining Tasks
- Push backend Docker image to ECR and trigger ECS deployment
- Create ECS task def + service for site vitrine (stepora.net)
- Configure Celery worker as separate ECS service
- Set up SES for email sending
- Migrate database data from VPS PostgreSQL to RDS
