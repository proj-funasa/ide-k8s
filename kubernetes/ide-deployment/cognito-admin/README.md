# Cognito Admin IESB IDE

## Português

Ferramenta de administração de usuários no Cognito User Pool utilizado pela IDE (ide.dataiesb.com).

### Pré-requisitos

- Python 3
- AWS CLI

### Instalar Dependências

```bash
pip install boto3 streamlit
```

### Configuração

1. Crie o usuário IAM com permissões restritas:

```bash
./create-user.sh
```

2. Configure o perfil AWS com as chaves geradas:

```bash
aws configure --profile cognito_admin_iesb
```

3. Execute a aplicação:

```bash
streamlit run cognito_admin.py
```

### Permissões IAM

O usuário `cognito_admin_iesb` possui acesso apenas a:

- `cognito-idp:ListUsers`
- `cognito-idp:AdminCreateUser`
- `cognito-idp:AdminDeleteUser`

Restrito ao user pool `us-east-1_KsQSqvc9B`.

---

## English

Admin tool for managing users in the Cognito User Pool used by the IDE (ide.dataiesb.com).

### Prerequisites

- Python 3
- AWS CLI

### Install Dependencies

```bash
pip install boto3 streamlit
```

### Setup

1. Create the IAM user with restricted permissions:

```bash
./create-user.sh
```

2. Configure the AWS profile with the generated access keys:

```bash
aws configure --profile cognito_admin_iesb
```

3. Run the app:

```bash
streamlit run cognito_admin.py
```

### IAM Permissions

The `cognito_admin_iesb` user only has access to:

- `cognito-idp:ListUsers`
- `cognito-idp:AdminCreateUser`
- `cognito-idp:AdminDeleteUser`

Scoped to the user pool `us-east-1_KsQSqvc9B`.
