# Roteiro de Demonstração (até 15 minutos)

1. **Contexto (1 min):** apresentar o desafio de monitorar talhões agrícolas, irrigação e condições ambientais.
2. **Arquitetura (3 min):** exibir `arquitetura.md`; destacar API Gateway, chaves distintas e bancos isolados por serviço.
3. **Inicialização (1 min):** executar `docker compose up --build`.
4. **Swagger (1 min):** abrir `http://localhost:8000/docs` e mostrar que somente o Gateway é público.
5. **Autenticação (2 min):** chamar uma rota sem `X-API-Key` (HTTP 401) e repetir com chave válida.
6. **Alerta de irrigação (3 min):** enviar umidade do solo de 18% e consultar `/api/v1/alerts` para ver o alerta `warning`.
7. **Alerta crítico (1 min):** enviar temperatura de 41 °C ou fumaça detectada e mostrar alerta `critical`.
8. **Reconhecimento (1 min):** usar `PATCH /api/v1/alerts/{id}/acknowledge` e consultar alertas abertos novamente.
9. **Resiliência e AWS (2 min):** explicar timeout/503/504, persistência antes da avaliação e evolução para ECS/EKS, API Gateway, CloudWatch e IAM.

