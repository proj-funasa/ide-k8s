# Guia do Usuário — IDE Cloud

## Acesso

- URL: https://ide.dataiesb.com
- Autenticação via Cognito (email e senha fornecidos pelo administrador)

## Ferramentas Disponíveis

- Terminal com `kubectl` (já configurado para o namespace `ads-system`)
- AWS CLI
- eksctl
- Docker

## Criando Containers

**IMPORTANTE: Nunca crie containers que rodam como root.**

Sempre inclua o `securityContext` nos seus deployments:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minha-app
  namespace: ads-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minha-app
  template:
    metadata:
      labels:
        app: minha-app
    spec:
      containers:
      - name: minha-app
        image: minha-imagem:latest
        securityContext:
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
```

Se o container exigir um usuário específico, adicione `runAsUser`:

```yaml
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
```

## Expondo sua Aplicação

Por motivos de segurança, a IDE **não tem acesso a Ingress**. Você não pode criar ou modificar recursos de Ingress.

Para expor sua aplicação, crie um **Service** do tipo `ClusterIP`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minha-app-svc
  namespace: ads-system
spec:
  selector:
    app: minha-app
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

Após criar o Service, solicite ao administrador a criação do Ingress para rotear o tráfego externo.

## Recursos Permitidos

Você pode gerenciar os seguintes recursos no namespace `ads-system`:

| Recurso | Exemplos |
|---|---|
| Core | pods, services, configmaps, secrets, PVCs |
| Apps | deployments, replicasets, statefulsets, daemonsets |
| Batch | jobs, cronjobs |

## Recursos Bloqueados

- Ingress / NetworkPolicy (gerenciados pelo administrador)
- Qualquer recurso fora do namespace `ads-system`

## Comandos Úteis

```bash
# Listar pods
kubectl get pods

# Criar deployment
kubectl apply -f meu-deployment.yaml

# Ver logs
kubectl logs <nome-do-pod>

# Acessar terminal do pod
kubectl exec -it <nome-do-pod> -- /bin/sh

# Listar services
kubectl get svc
```

## Suporte

Em caso de dúvidas ou para solicitar criação de Ingress, entre em contato com o administrador.
