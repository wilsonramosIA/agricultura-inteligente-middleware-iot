# Relatório Técnico — Atividade Prática 01

**Disciplina:** Sistemas Distribuídos  
**Grupo:** 8 — Middleware para Microsserviços  
**Tema:** Monitoramento e Alertas de Sensores IoT em Agricultura Inteligente

## Objetivo

Implementar um middleware que intermedeie comunicação entre cliente e microsserviços, demonstrando autenticação, comunicação distribuída, desacoplamento, observabilidade e tratamento de falhas.

## Solução desenvolvida

Foram implementados três serviços REST em Python/FastAPI, executáveis por Docker Compose:

1. **API Gateway:** middleware do grupo e única porta de entrada pública.
2. **Serviço de Telemetria:** recebe e armazena leituras de sensores.
3. **Serviço de Alertas:** avalia regras e controla o ciclo de vida dos alertas.

O Gateway não conhece a persistência dos serviços e os clientes não acessam suas APIs internas. Isso reduz acoplamento e permite escalar cada componente separadamente.

![Monitoramento de fazenda e resposta a alertas](imagens/monitoramento-fazenda.png)

*Cenário ilustrativo adotado pela solução: sensores no campo coletam dados e a central monitora condições de risco à lavoura.*

## Comunicação distribuída

A solução usa HTTP/REST e JSON. `X-API-Key` autentica consumidores externos, enquanto `X-Internal-API-Key` protege chamadas entre serviços. Cada chamada possui timeout configurável. O Gateway produz um identificador de correlação (`X-Request-ID`) e registra método, rota, status e duração nos logs. Quando Alertas está indisponível, Telemetria persiste o evento em uma fila local e o reprocessa periodicamente, evitando a perda de alertas.

## Evidências dos requisitos

| Exigência | Evidência no projeto |
| --- | --- |
| Comunicação cliente-servidor | Rotas `/api/v1/*` do Gateway. |
| Middleware | Autenticação, roteamento, logs e correlação em `gateway/main.py`. |
| Banco de dados | SQLite isolado por microsserviço. |
| Segurança | Duas chaves distintas; rotas internas não aceitam chave de cliente. |
| Exceções e timeout | Respostas 401, 422, 503 e 504; timeout HTTP configurável. |
| Fallback | Fila SQLite de alertas pendentes, retentativas periódicas e `Retry-After` para o cliente. |
| Logs e timestamp | `logging` no Gateway e timestamps ISO 8601 UTC. |
| Swagger | `http://localhost:8000/docs`. |
| Testes | Casos em `tests/`, executados com `pytest`. |

## Vantagens

- Ponto único de entrada e políticas de segurança centralizadas.
- Separação de responsabilidades e dados por serviço.
- APIs pequenas, documentadas e testáveis.
- Contêineres tornam a demonstração reproduzível.
- Caminho de evolução claro para serviços AWS.

## Limitações e trabalhos futuros

- Transporte interno síncrono aumenta dependência da disponibilidade de Alertas.
- SQLite não é indicado para alta concorrência em produção.
- API Key é básica; JWT/OAuth2 e rotação de segredos seriam melhorias importantes.
- Eventos pendentes após falha ainda não são reprocessados automaticamente; uma fila SQS com DLQ resolveria esse ponto.

## Conclusão

O projeto demonstra o papel do middleware como camada de mediação: centraliza preocupações transversais e desacopla clientes dos detalhes internos. A arquitetura atende à atividade e pode evoluir gradualmente para ECS/EKS, API Gateway, CloudWatch e IAM.
