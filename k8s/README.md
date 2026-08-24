# Equinix MCP — Kubernetes deployment

Las credenciales viven **fuera de los manifests** (en un `Secret` de K8s) y se
inyectan al pod como variables de entorno. Los manifests no llevan secretos.

## 1. Pushear la imagen a un registry

El cluster necesita poder tirar la imagen. Elegí uno:

```bash
# Docker Hub (o GHCR, Harbor, ECR, etc.)
docker tag equinix-mcp:latest <registry>/<user>/equinix-mcp:0.1.0
docker push <registry>/<user>/equinix-mcp:0.1.0
```

Y actualizá `image:` en `deployment.yaml`.

## 2. Crear el Secret (creds nunca en git)

**Opción A — desde CLI con `--from-literal`** (una línea por var):

```bash
kubectl create secret generic equinix-mcp-secrets \
  --from-literal=EQUINIX_CLIENT_ID='...' \
  --from-literal=EQUINIX_CLIENT_SECRET='...' \
  --from-literal=MCP_SERVER_API_KEY='emcp-...'
```

**Opción B — desde el `.env` existente**:

```bash
kubectl create secret generic equinix-mcp-secrets --from-env-file=../.env
```

**Opción C — sealed-secrets / SOPS** (production):

Encriptar `secret.yaml` con sealed-secrets o SOPS y commitear la versión
sellada. El cluster desencripta al deploy. No incluido acá pero es el patrón
correcto para GitOps.

## 3. Aplicar el resto de los manifests

```bash
kubectl apply -k .
```

O individual:

```bash
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
```

## 4. Verificar

```bash
kubectl get pods -l app=equinix-mcp
kubectl logs -l app=equinix-mcp --tail 20
kubectl port-forward svc/equinix-mcp 8081:8080
# En otra terminal:
curl -H "Authorization: Bearer $(kubectl get secret equinix-mcp-secrets -o jsonpath='{.data.MCP_SERVER_API_KEY}' | base64 -d)" \
     -X POST http://127.0.0.1:8081/mcp/ \
     -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
     --data '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"qa","version":"1"}}}'
```

## 5. Rotar credenciales sin rebuild

```bash
kubectl create secret generic equinix-mcp-secrets \
  --from-literal=EQUINIX_CLIENT_ID='NEW' \
  --from-literal=EQUINIX_CLIENT_SECRET='NEW' \
  --from-literal=MCP_SERVER_API_KEY='emcp-NEW' \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/equinix-mcp
```

## Exponer fuera del cluster

Por defecto el Service es `ClusterIP` (interno). Para exponerlo:

- **NodePort**: cambiar `spec.type` a `NodePort` y agregar `nodePort: 30081`
- **LoadBalancer**: cambiar a `LoadBalancer` (requiere cloud provider)
- **Ingress**: recomendado con TLS terminado en el ingress controller

## Cómo se ven las creds dentro del pod

```bash
kubectl exec -it deploy/equinix-mcp -- env | grep -E '^(EQUINIX_|MCP_)'
```

Deberías ver las 3 vars del Secret + los defaults `MCP_PORT`, `MCP_HOST`,
`MCP_HOST_IP`.
