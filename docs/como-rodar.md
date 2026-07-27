# Como Rodar o Projeto

Este guia executa o sistema de Agricultura Inteligente localmente. A forma recomendada é Docker Compose, pois inicia todos os microsserviços com uma única instrução.

## Opção 1 — Docker Compose (recomendada)

### Pré-requisitos

- Docker Desktop instalado e em execução.
- Porta `8000` disponível no computador.

### Passos

No diretório raiz do projeto, crie o arquivo de variáveis de ambiente e suba os contêineres:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Na primeira execução, o Docker baixa a imagem Python e instala as dependências. Aguarde a inicialização dos serviços:

- API Gateway: `http://localhost:8000`
- Serviço de Telemetria: interno, porta `8001`
- Serviço de Alertas: interno, porta `8002`

Abra a documentação interativa da API em `http://localhost:8000/docs`.

Para executar em segundo plano, use:

```powershell
docker compose up --build -d
```

Para acompanhar os logs do Gateway:

```powershell
docker compose logs -f api-gateway
```

Para encerrar os contêineres sem apagar os dados:

```powershell
docker compose down
```

Para encerrar e apagar os bancos de dados de demonstração:

```powershell
docker compose down -v
```

## Opção 2 — Execução local com Python

### Pré-requisitos

- Python 3.12 ou superior.
- Três terminais PowerShell abertos no diretório raiz do projeto.

### Instalação

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Inicie um serviço por terminal, respeitando as portas abaixo:

```powershell
# Terminal 1
uvicorn alerts.main:app --host 0.0.0.0 --port 8002 --reload

# Terminal 2
uvicorn telemetry.main:app --host 0.0.0.0 --port 8001 --reload

# Terminal 3
uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload
```

## Teste funcional rápido

Com os serviços em execução, envie uma medição de baixa umidade do solo. A API Key padrão da demonstração é `grupo8-demo-key`.

```powershell
$headers = @{ "X-API-Key" = "grupo8-demo-key" }
$body = @{
  sensor_id = "solo-talhao-01"
  metric = "soil_moisture"
  value = 18
  unit = "%"
  location = "Talhão Norte"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/telemetry -Headers $headers -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Get -Uri http://localhost:8000/api/v1/alerts -Headers $headers
```

O primeiro comando registra a leitura; o segundo deve exibir um alerta `warning` recomendando irrigação.

## Simular sensor offline

O limite padrão de heartbeat é 300 segundos. Para uma demonstração rápida, altere no arquivo `.env`:

```text
SENSOR_OFFLINE_THRESHOLD_SECONDS=30
```

Reinicie os contêineres, envie uma leitura e aguarde mais de 30 segundos. A verificação periódica criará um alerta crítico `sensor_offline`. Assim que o mesmo sensor enviar nova telemetria, esse alerta será reconhecido automaticamente.

## Executar os testes automatizados

Com o ambiente virtual ativo:

```powershell
pytest -q
```

## Problemas comuns

| Situação | Solução |
| --- | --- |
| `docker compose` não é reconhecido | Inicie/instale o Docker Desktop e abra um novo terminal. |
| Porta 8000 ocupada | Encerre o processo que usa a porta ou altere o mapeamento em `docker-compose.yml`. |
| Resposta HTTP 401 | Envie o cabeçalho `X-API-Key: grupo8-demo-key`. |
| Resposta HTTP 503 ou 504 | Confirme que os serviços de Telemetria e Alertas foram iniciados antes do Gateway. |
| Serviço de Alertas indisponível | A leitura permanece salva e a avaliação entra na fila persistente; o serviço tenta reenviá-la a cada 30 segundos. |
| API não abre no navegador | Confirme `http://localhost:8000/health` e consulte os logs com `docker compose logs`. |
