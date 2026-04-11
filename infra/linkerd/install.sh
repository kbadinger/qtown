#!/bin/bash
# install.sh — Install Linkerd CLI, control plane, and inject sidecars into qtown namespace.
#
# Usage:
#   chmod +x infra/linkerd/install.sh
#   ./infra/linkerd/install.sh
#
# Requirements:
#   - kubectl configured to point at the target cluster
#   - curl available
#   - Internet access to run.linkerd.io

set -euo pipefail

NAMESPACE="${QTOWN_NAMESPACE:-qtown}"
LINKERD_VERSION="${LINKERD_VERSION:-stable-2.14.10}"

echo "==> Installing Linkerd CLI (version: ${LINKERD_VERSION})"
curl --proto '=https' --tlsv1.2 -sSfL https://run.linkerd.io/install | \
  LINKERD2_VERSION="${LINKERD_VERSION}" sh

# Add linkerd to PATH for this session
export PATH="${HOME}/.linkerd2/bin:${PATH}"

echo "==> Verifying Linkerd CLI"
linkerd version --client

echo "==> Pre-flight checks"
linkerd check --pre

echo "==> Installing Linkerd CRDs"
linkerd install --crds | kubectl apply -f -

echo "==> Installing Linkerd control plane"
linkerd install \
  --proxy-memory-request="32Mi" \
  --proxy-memory-limit="128Mi" \
  --proxy-cpu-request="10m" \
  --proxy-cpu-limit="100m" | \
  kubectl apply -f -

echo "==> Waiting for control plane to be ready"
linkerd check

echo "==> Ensuring namespace '${NAMESPACE}' exists"
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

echo "==> Annotating namespace for automatic proxy injection"
kubectl annotate namespace "${NAMESPACE}" \
  linkerd.io/inject=enabled \
  --overwrite

echo "==> Injecting Linkerd sidecars into all deployments in '${NAMESPACE}'"
kubectl get deploy -n "${NAMESPACE}" -o yaml | \
  linkerd inject - | \
  kubectl apply -f -

echo "==> Applying service profiles from infra/linkerd/service-profiles/"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for profile in "${SCRIPT_DIR}/service-profiles/"*.yaml; do
  echo "  Applying: ${profile}"
  kubectl apply -f "${profile}" -n "${NAMESPACE}"
done

echo "==> Applying authorization policies"
kubectl apply -f "${SCRIPT_DIR}/authorization-policies.yaml" -n "${NAMESPACE}"

echo "==> Final Linkerd health check"
linkerd check

echo ""
echo "Linkerd installation complete for namespace '${NAMESPACE}'."
echo "Dashboard: run 'linkerd viz dashboard' to open the Linkerd dashboard."
