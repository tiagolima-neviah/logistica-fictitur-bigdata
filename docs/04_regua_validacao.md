<a id="topo"></a>

# Régua de Validação — o contrato de aceite dos dados sintéticos

<!-- nav:start -->
[Home](../README.md) | [← Modelo de Dados](03_modelo_dados_staging.md) | [Guia de Reprodução →](05_guia_reproducao.md)
<!-- nav:end -->

> Antes de qualquer camada analítica consumir o staging, os dados sintéticos passam por uma régua de validação versionada: um conjunto de verificações com bandas de aceite (mínimo e máximo) para volumes, indicadores, fases, taxas de sujeira e margens. A regra é inegociável: **banda estourada não se contorna, regenera-se a base**. Este documento explica o mecanismo; as bandas vivem em código, no repositório, e todo ajuste é versionado.

## 1. Por que uma régua

Dado sintético sem contrato de aceite é dado inventado duas vezes: uma no gerador, outra na cabeça de quem analisa. A régua fecha esse buraco: ela declara, ANTES de o gerador rodar em escala, o que a base precisa exibir para ser aceita (quantos pedidos por mês em cada ano, qual OTIF em cada fase da história, quanta sujeira de cada tipo, que margens por linha de serviço). Se a base gerada foge do contrato, o defeito é do gerador, e o gerador é corrigido e a base regerada; nunca se "ajeita" o dado depois de pronto. O mesmo mecanismo serve de verificação de regressão: qualquer mudança futura no gerador roda a régua de novo.

## 2. O que a régua verifica (28 checks na v1)

- **Volumes:** média de pedidos/mês por ano (com a tendência de crescimento do arco 2020-2026), itens por pedido e o total da maior tabela fato.
- **O arco da história:** OTIF geral por ano seguindo a narrativa do negócio (ruim em 2020, oscilando até 2023, virada em 2024, excelência em 2025-2026), o piso de OTIF do pior cliente relevante em 2020 e a concentração de volume nos maiores clientes.
- **Fases do pedido:** presença universal da fase EA, incidência parcial das fases esporádicas (DC e EX) e coerência entre fase atual e desfecho (pedido em EC precisa ter data de entrega).
- **Catálogo de sujeira:** as taxas de defeito proposital dentro das faixas planejadas (datas-sentinela, agendamentos sem chegada, itens sem valor unitário, pedidos órfãos de item).
- **Margens:** MC% de transporte e de armazenagem dentro de faixas plausíveis, calculadas das faturas, custos e parâmetros financeiros (nunca digitadas).

## 3. Como rodar

Com o staging de pé (ver [README](../README.md)) e o ambiente Python instalado (`uv sync`):

```bash
uv run regua-staging
```

A saída lista cada check com o valor observado, a banda e o veredito, e o processo termina com código de saída 1 se qualquer check reprovar (pronto para CI). Contra um banco vazio, a régua reprova tudo, que é o comportamento esperado: ela existe justamente para só liberar o staging populado e dentro do contrato.

## 4. Onde vivem as bandas

Em [`src/logistica_fictitur/validacao/bandas.py`](../src/logistica_fictitur/validacao/bandas.py), com um comentário por grupo explicando a intenção. As bandas da v1 são deliberadamente largas; a calibração fina acontece nas primeiras rodadas do gerador e cada estreitamento é um commit revisado, nunca um ajuste silencioso.

---

[Início](#topo)
