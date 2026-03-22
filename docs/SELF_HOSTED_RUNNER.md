# Self-Hosted GitHub Actions Runner on VPS

## Why

GitHub Actions billing is blocked (payment failure / spending limit). Self-hosted runners
provide **unlimited free minutes** at $0 cost, using your existing VPS resources.

**VPS specs**: 2 vCPU, 8 GB RAM, 96 GB disk (42 GB free), Docker + AWS CLI + Node 22 + jq
already installed. This is more than enough.

## Architecture

```
GitHub push → GitHub detects self-hosted runner → Runner on VPS picks up job →
  Build Docker image locally → Push to ECR → Update ECS task definitions → Done
```

The runner agent is a lightweight daemon (~200 MB RAM) that polls GitHub for jobs. When a
workflow uses `runs-on: self-hosted`, GitHub routes the job to your VPS instead of a
hosted runner.

## Setup (One-Time, ~10 Minutes)

### 1. Create a dedicated user (security best practice)

```bash
sudo useradd -m -s /bin/bash github-runner
sudo usermod -aG docker github-runner
```

### 2. Download and install the runner

Go to **each** GitHub repo → Settings → Actions → Runners → New self-hosted runner.
GitHub will show a token. You need one runner per repo, OR one runner with labels that
all 3 repos share (easier: one runner configured on the **org** level or per-repo).

The simplest approach: **3 separate runner instances**, one per repo.

#### Backend runner

```bash
# As root
mkdir -p /opt/github-runners/stepora-backend
cd /opt/github-runners/stepora-backend

# Download latest runner (check https://github.com/actions/runner/releases for version)
RUNNER_VERSION="2.322.0"
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

# Configure (use the token from GitHub Settings > Actions > Runners > New self-hosted runner)
./config.sh --url https://github.com/kingoftech-v01/stepora-backend \
  --token YOUR_TOKEN_HERE \
  --name "vps-backend" \
  --labels "self-hosted,linux,x64,vps" \
  --work "_work" \
  --unattended

# Install as systemd service (runs on boot, auto-restarts)
sudo ./svc.sh install
sudo ./svc.sh start
sudo ./svc.sh status
```

#### Frontend runner

```bash
mkdir -p /opt/github-runners/stepora-frontend
cd /opt/github-runners/stepora-frontend

RUNNER_VERSION="2.322.0"
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

./config.sh --url https://github.com/kingoftech-v01/stepora-frontend \
  --token YOUR_TOKEN_HERE \
  --name "vps-frontend" \
  --labels "self-hosted,linux,x64,vps" \
  --work "_work" \
  --unattended

sudo ./svc.sh install
sudo ./svc.sh start
```

#### Site runner

```bash
mkdir -p /opt/github-runners/stepora-site
cd /opt/github-runners/stepora-site

RUNNER_VERSION="2.322.0"
curl -o actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz -L \
  https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
tar xzf actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz
rm actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz

./config.sh --url https://github.com/kingoftech-v01/stepora-site \
  --token YOUR_TOKEN_HERE \
  --name "vps-site" \
  --labels "self-hosted,linux,x64,vps" \
  --work "_work" \
  --unattended

sudo ./svc.sh install
sudo ./svc.sh start
```

### 3. Ensure AWS credentials are available to the runner

The runner inherits the system AWS config. Verify:

```bash
aws sts get-caller-identity
# Should return account 987409845802
```

If running as `github-runner` user, copy credentials:

```bash
sudo mkdir -p /home/github-runner/.aws
sudo cp /root/.aws/config /home/github-runner/.aws/
sudo cp /root/.aws/credentials /home/github-runner/.aws/
sudo chown -R github-runner:github-runner /home/github-runner/.aws
```

### 4. Verify runners are online

Go to each GitHub repo → Settings → Actions → Runners. Each runner should show
as **Idle** (green dot).

## Workflow Changes

Change `runs-on: ubuntu-latest` to `runs-on: self-hosted` in each workflow file.

### Backend: `.github/workflows/deploy-backend.yml`

```yaml
# Before
runs-on: ubuntu-latest

# After
runs-on: self-hosted
```

Apply to ALL jobs in the file (`test`, `build-and-push`, `deploy`).

### Frontend: `.github/workflows/deploy-frontend.yml`

Same change for all jobs (`lint`, `build`, `deploy`).

### Site: `.github/workflows/deploy-site.yml`

Same change for all jobs (`lint`, `build-and-push`, `deploy`).

### Important: Self-hosted runners keep state

Unlike GitHub-hosted runners, self-hosted runners **persist** between jobs. This means:
- Docker images from previous builds are cached (faster builds, but disk fills up)
- Node modules may be cached
- Python venvs may persist

**Add cleanup** at the end of workflows or set up a cron job:

```bash
# /etc/cron.daily/cleanup-github-runner (as root)
#!/bin/bash
# Prune Docker images older than 7 days
docker image prune -a --filter "until=168h" -f
# Prune build cache
docker builder prune -f --filter "until=168h"
```

```bash
chmod +x /etc/cron.daily/cleanup-github-runner
```

## GitHub Secrets on Self-Hosted Runner

When using self-hosted runners, GitHub Secrets still work normally. The runner agent
receives secrets from GitHub at job execution time. No changes needed to secret
configuration.

However, for the VPS deploy script (Option 3), AWS credentials come from the local
AWS CLI config instead of GitHub Secrets.

## Resource Impact on VPS

| Resource | Idle runner | During backend build | During frontend build |
|----------|-------------|---------------------|-----------------------|
| RAM      | ~200 MB     | ~1.5 GB (Docker)    | ~800 MB (Node)        |
| CPU      | 0%          | 100% (2 cores)      | 80% (1-2 cores)       |
| Disk     | ~600 MB     | +2 GB (temp)        | +500 MB (temp)        |
| Duration | -           | ~3-5 min            | ~1-2 min              |

The VPS has 8 GB RAM and 2 CPUs. Builds will temporarily use most resources, but preprod
services will continue running (just slower during builds).

**Recommendation**: Schedule deploys during low-traffic hours, or stop preprod containers
temporarily during production builds if resources are tight.

## Troubleshooting

### Runner shows "Offline"

```bash
# Check service status
sudo systemctl status actions.runner.kingoftech-v01-stepora-backend.vps-backend.service

# Restart
sudo systemctl restart actions.runner.kingoftech-v01-stepora-backend.vps-backend.service

# Check logs
journalctl -u actions.runner.kingoftech-v01-stepora-backend.vps-backend.service -n 50
```

### Docker permission denied

```bash
sudo usermod -aG docker github-runner
# Then restart the runner service
```

### Disk space issues

```bash
# Check disk usage
df -h /
docker system df

# Aggressive cleanup
docker system prune -a -f
```

### Runner token expired

Tokens expire after 1 hour. If `config.sh` fails, generate a new token from
GitHub Settings → Actions → Runners → New self-hosted runner.

## Removing a Runner

```bash
cd /opt/github-runners/stepora-backend
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove --token YOUR_REMOVE_TOKEN
```

Get the remove token from GitHub Settings → Actions → Runners → (select runner) → Remove.
