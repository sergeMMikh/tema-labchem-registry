# LabChem Registry

[English](README.md) · **Português**

Sistema de registo, pesquisa e localização de reagentes químicos para laboratórios, com acesso através de uma interface web na rede local e, futuramente, através de bots no Telegram e WhatsApp.

> **Estado do projeto:** em planeamento; a implementação ainda não foi iniciada.

## Objetivo

O LabChem Registry centraliza o inventário de reagentes químicos da instituição numa única aplicação e base de dados alojadas na rede interna. Cada embalagem ou unidade física é registada individualmente, permitindo encontrá-la pela respetiva identificação e localização.

## Funcionalidades previstas

- Pesquisa por nome completo ou parcial, número CAS, fabricante, referência de catálogo ou laboratório.
- Localização física no formato **laboratório → armário → prateleira**.
- Registo manual de novos reagentes.
- Registo por fotografia do rótulo, com extração preliminar de dados.
- Confirmação e correção obrigatórias dos dados reconhecidos antes de guardar.
- Edição de fichas de acordo com as permissões do utilizador.
- Movimentação de reagentes entre localizações.
- Abate de unidades consumidas ou indisponíveis, sem eliminar o respetivo registo.
- Identificação por fotografia para localizar uma ficha existente antes do abate.
- Histórico das operações relevantes.
- Acesso por interface web, bot Telegram e bot WhatsApp através do mesmo backend.

O sistema não controla consumos parciais nem a quantidade restante de uma embalagem.

## Ficha do reagente

Cada unidade física terá uma ficha própria com os seguintes dados:

- nome;
- número CAS, quando disponível;
- fabricante;
- referência ou número de catálogo, quando disponível;
- concentração, pureza ou grau, quando aplicável;
- laboratório, armário e prateleira;
- fotografia do rótulo;
- estado;
- observações adicionais.

Os campos obrigatórios serão limitados ao necessário para identificar e localizar o reagente.

## Regras essenciais

- A pesquisa normal apresenta apenas reagentes disponíveis.
- O reconhecimento de um rótulo nunca cria definitivamente uma ficha sem confirmação humana.
- No processo de abate, o reconhecimento procura uma unidade já registada; não cria uma nova.
- O abate altera o estado da unidade, preservando a ficha e o histórico.
- As alterações à base de dados ficam associadas ao utilizador responsável.

## Utilizadores e permissões

Estão previstos três perfis iniciais:

- **Utilizador:** consulta e operações correntes autorizadas.
- **Responsável de laboratório:** gestão dos reagentes e localizações sob a sua responsabilidade.
- **Administrador:** gestão de utilizadores, laboratórios e dados de referência.

A matriz final de permissões será definida durante a fase de projeto.

## Arquitetura prevista

```text
Interface web ─┐
Bot Telegram ──┼── API/backend comum ── PostgreSQL na rede interna
Bot WhatsApp ──┘          │
                          ├── reconhecimento de rótulos
                          ├── autenticação e permissões
                          └── histórico de operações
```

A base de dados principal deverá permanecer na infraestrutura interna. Apenas as comunicações necessárias ao funcionamento dos serviços Telegram e WhatsApp serão externas.

## Fases propostas

1. Modelação dos dados, API, utilizadores e localizações.
2. Implementação da base de dados e do backend local.
3. Desenvolvimento da interface web para a rede local.
4. Integração do bot Telegram.
5. Reconhecimento de rótulos através de fotografia.
6. Integração do bot WhatsApp.
7. Testes em laboratório, ajustes e entrada em produção.

A arquitetura deverá permitir a adoção futura de identificadores internos e códigos QR, embora estes não façam parte da primeira versão obrigatória.

## Licença

Ainda não foi definida uma licença.
