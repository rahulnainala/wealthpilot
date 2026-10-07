# Kubernetes manifests (stretch artifact)

Illustrative manifests mirroring the docker-compose topology. These are **not** part of the
primary deploy path (Vercel + Railway/Render + Route53 — see the root README); they demonstrate how
the same four services map onto Kubernetes.

Key property preserved from compose: the **risk-engine has a `ClusterIP` Service only** — it is
reachable inside the cluster (by the backend) but never exposed via the Ingress.

## Apply

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config.yaml        # edit the Secret first
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/risk-engine.yaml
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml
kubectl apply -f k8s/ingress.yaml
```

Build and push images first (`wealthpilot/backend`, `wealthpilot/frontend`,
`wealthpilot/risk-engine`) and update the `image:` fields to your registry.
