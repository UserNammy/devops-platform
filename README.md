# devops-platform

A small URL shortener API taken from code to production: containerised, tested and scanned in CI, deployed with GitOps to a k3s cluster on a Hetzner Cloud VPS, with Prometheus and Grafana monitoring.

The application is deliberately simple. The point of this project is everything around it.

## Architecture

```mermaid
flowchart LR
    dev[Developer] -->|git push| gh[GitHub repo]

    subgraph ci[GitHub Actions]
        lint[ruff] --> test[pytest + PostgreSQL]
        test --> build[docker build]
        build --> scan[Trivy scan]
        scan -->|main only| push[push image]
        iac["terraform fmt/validate<br/>helm lint"]
    end

    gh --> ci
    push --> ghcr[(GHCR)]

    subgraph hetzner[Hetzner Cloud]
        fw[Cloud firewall] --> vps
        subgraph vps["VPS: Ubuntu 24.04, hardened by Ansible"]
            subgraph k3s[k3s]
                traefik[Traefik ingress] --> svc[shortener Service]
                svc --> pods["shortener pods<br/>HPA 2-5"]
                pods --> pg[(PostgreSQL)]
                argo[Argo CD]
                prom[Prometheus] -->|scrape /metrics| pods
                graf[Grafana] --> prom
                am[Alertmanager] --- prom
            end
        end
    end

    tf[Terraform] -->|provisions| hetzner
    ansible[Ansible] -->|hardens + installs k3s| vps
    argo -->|watches k8s/ chart| gh
    argo -->|syncs| pods
    pods -.->|pull| ghcr
    user[Users] -->|HTTPS| fw
```

## Repository layout

| Path | Contents |
| --- | --- |
| `app/` | FastAPI service, pytest suite, multi-stage `Dockerfile` |
| `docker-compose.yml` | Local stack: API + PostgreSQL |
| `.github/workflows/ci.yml` | Lint, test, IaC validation, image build, Trivy scan, push to GHCR |
| `infra/terraform/` | Hetzner Cloud server, firewall and SSH key |
| `infra/ansible/` | Server hardening (SSH, ufw, fail2ban, unattended-upgrades) and k3s install |
| `k8s/charts/shortener/` | Helm chart: Deployment, Service, Ingress, HPA, ConfigMap, Secret, ServiceMonitor |
| `k8s/argocd/` | Argo CD `Application` for GitOps delivery |
| `monitoring/` | kube-prometheus-stack values, Grafana dashboard, PrometheusRule |

## The application

`shortener` is a URL shortener backed by PostgreSQL.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/links` | Create a short link (`{"url": "...", "code": "optional-alias"}`) |
| `GET` | `/api/links/{code}` | Link details and click count |
| `DELETE` | `/api/links/{code}` | Delete a link |
| `GET` | `/{code}` | Redirect (307) to the target URL |
| `GET` | `/health` | Liveness probe (process is up) |
| `GET` | `/ready` | Readiness probe (database reachable) |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/docs` | OpenAPI UI |

Metrics exposed: `http_requests_total` and `http_request_duration_seconds` labelled by route template (not raw path, so cardinality stays bounded), plus the business counters `shortener_links_created_total` and `shortener_redirects_total`.

## Quickstart

### Run locally with Docker Compose

```bash
cp .env.example .env        # then set POSTGRES_PASSWORD
docker compose up --build
curl -X POST localhost:8000/api/links -H 'content-type: application/json' \
     -d '{"url": "https://github.com", "code": "gh-home"}'
curl -i localhost:8000/gh-home
```

Open http://localhost:8000/docs for the interactive API.

### Run the tests

```bash
cd app
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && pytest
```

Tests use SQLite by default. Set `TEST_DATABASE_URL` to run them against PostgreSQL, as CI does. You can also run lint and tests inside the image build with `make test-docker`.

Run `make help` to list all targets.

### Deploy to Hetzner

Requirements: Terraform >= 1.9, Ansible, kubectl, Helm and a Hetzner Cloud API token.

```bash
# 1. Provision the server
export HCLOUD_TOKEN=...                       # never commit it
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
make tf-init tf-plan tf-apply
terraform -chdir=infra/terraform output -raw ansible_inventory > infra/ansible/inventory/hosts.ini

# 2. Harden it and install k3s (writes infra/ansible/kubeconfig, git-ignored)
make ansible-bootstrap   # first run as root: creates the deploy user
make ansible             # SSH hardening, ufw, fail2ban, unattended-upgrades, k3s
export KUBECONFIG=$PWD/infra/ansible/kubeconfig

# 3. Monitoring
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
kubectl create namespace monitoring
kubectl -n monitoring create secret generic grafana-admin \
  --from-literal=admin-user=admin --from-literal=admin-password="$(openssl rand -base64 24)"
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  -n monitoring -f monitoring/kube-prometheus-stack/values.yaml
kubectl apply -k monitoring/

# 4. Argo CD and the application
kubectl create namespace argocd
kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl create namespace shortener
kubectl -n shortener create secret generic shortener-db \
  --from-literal=DATABASE_URL='postgresql+psycopg://user:password@host:5432/shortener'
kubectl apply -f k8s/argocd/application.yaml
```

Before deploying, replace `sho.example.com` with your domain. After the first `terraform init`, commit the generated `.terraform.lock.hcl` so every run uses the same provider build.

## Tech choices

**Hetzner Cloud + k3s instead of a managed Kubernetes service: cost.** A managed control plane on the big clouds is billed before a single workload runs (EKS is $0.10/hour, about $73/month, for the control plane alone), plus worker nodes, load balancer and NAT gateway. A small Hetzner shared-vCPU server costs single-digit euros per month and k3s, a CNCF-certified lightweight Kubernetes distribution, runs comfortably on it. For a portfolio project or a small production service this is the difference between paying for the platform and paying for the app. The trade-off is that I operate the node myself (OS patching, hardening, backups), which is exactly what the Ansible part covers.

**FastAPI + SQLAlchemy + PostgreSQL.** Typed request validation, auto-generated OpenAPI docs, and a boring, reliable database. Settings come from environment variables (12-factor), so the same image runs in Compose, CI and Kubernetes.

**Multi-stage Docker build.** Dependencies are installed into a virtualenv in a builder stage and only that venv plus the source are copied into a `python:3.12-slim` runtime. The container runs as a fixed non-root UID (10001), which lets Kubernetes enforce `runAsNonRoot` with a read-only root filesystem. A separate `test` stage runs ruff and pytest against the exact dependency set that ships.

**GitHub Actions + GHCR.** No extra service to run or pay for; the registry is authorised with the workflow's own `GITHUB_TOKEN`. Third-party actions are pinned to full commit SHAs, permissions are least-privilege per job, and images are only pushed from `main` after tests and the Trivy gate pass. Images are tagged with the commit SHA for traceable, immutable deploys and ship with SBOM and provenance attestations.

**Trivy.** Scans the built image for OS and Python vulnerabilities. Results go to the GitHub Security tab (SARIF), and the build fails on fixable HIGH or CRITICAL findings.

**Terraform.** The server, firewall and SSH key are declared in code and reproducible. The cloud firewall only exposes 80/443 publicly; SSH and the Kubernetes API are restricted to admin CIDRs. State is local for now with a ready-to-uncomment S3 backend (Hetzner Object Storage) for team use.

**Ansible.** Idempotent, agentless configuration of the OS: key-only SSH with root login disabled, ufw as a second firewall layer, fail2ban, automatic security updates and a pinned k3s version.

**Helm + Argo CD.** Helm packages the Kubernetes manifests with per-environment values; Argo CD pulls from Git and continuously reconciles the cluster (pull-based GitOps), so the cluster never needs to accept credentials from CI and drift is corrected automatically.

**kube-prometheus-stack.** One chart for Prometheus, Alertmanager, Grafana, node-exporter and kube-state-metrics. The app is discovered through a `ServiceMonitor`, its dashboard is loaded by the Grafana sidecar from a labelled ConfigMap, and a `PrometheusRule` alerts when more than 5% of requests fail.

## Security notes

- No secrets in the repository. Local values live in `.env` (git-ignored, see `.env.example`); Terraform reads `HCLOUD_TOKEN` from the environment; Kubernetes reads the database URL from a Secret created out of band. The placeholder Secret in the chart is only rendered when `secret.existingSecret` is empty.
- Pods run as non-root with all capabilities dropped, no privilege escalation, a read-only root filesystem, the `RuntimeDefault` seccomp profile and no service account token mounted.
- CI uses least-privilege `GITHUB_TOKEN` permissions and SHA-pinned actions.

## Roadmap

Done:

- [x] FastAPI service with health, readiness and Prometheus metrics
- [x] Test suite running against PostgreSQL in CI
- [x] Multi-stage, non-root Docker image and local Compose stack
- [x] CI: lint, tests, IaC validation, image build, Trivy scan, push to GHCR
- [x] Terraform for the Hetzner server and firewall
- [x] Ansible hardening and k3s install
- [x] Helm chart and Argo CD Application
- [x] Monitoring stack values, dashboard and alert rule

Next:

- [ ] First apply against a live Hetzner server and record a demo
- [ ] Database migrations with Alembic instead of `create_all` at startup
- [ ] Run PostgreSQL in the cluster with CloudNativePG, with scheduled backups to object storage
- [ ] cert-manager with Let's Encrypt for TLS on the ingress
- [ ] Manage secrets with Sealed Secrets or External Secrets instead of `kubectl create secret`
- [ ] Automatic image tag bumps (Argo CD Image Updater or a CI commit to `values-prod.yaml`)
- [ ] Remote Terraform state with locking, and `terraform plan` on pull requests
- [ ] `ansible-lint` in CI and Molecule tests for the roles
- [ ] Centralised logs with Loki
- [ ] SLO-based alerting (error budget burn rate) and an Alertmanager receiver
- [ ] Staging environment with its own Argo CD Application

## License

[MIT](LICENSE)
