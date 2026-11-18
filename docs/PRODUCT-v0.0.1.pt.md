# LabChem Registry v0.0.1

**Data de lançamento:** 18 de novembro de 2026  
**Estado:** MVP inicial para gestão interna do inventário

O LabChem Registry é uma aplicação Django para localizar e gerir o stock de reagentes laboratoriais. Os dados do reagente são guardados separadamente das embalagens físicas e das respetivas localizações.

## Funcionalidades atuais

- Pesquisar por nome do reagente, fórmula, número CAS, fornecedor, referência de catálogo ou código de barras. Filtrar por laboratório, folha de origem, localização e estado do stock; ordenar e paginar resultados.
- Consultar detalhes dos reagentes e embalagens, quantidades disponíveis, localizações, validade, ligações para FDS e histórico de movimentos.
- Adicionar reagentes e embalagens; registar consumo, mover embalagens ou abatê-las. As alterações ao stock ficam no histórico e exigem a permissão Django correspondente.
- Consultar a árvore de localizações, os totais do painel e a lista de atenção, que assinala stock baixo, embalagens pendentes ou não encontradas, localização ou FDS em falta e validade nos próximos 90 dias.
- Exportar o inventário para XLSX e consultar a lista JSON apenas de leitura em `/api/v1/reagents/` (até 100 resultados por pedido).
- Gerir utilizadores e permissões na administração Django. Os grupos configurados são Viewer, Laboratory user e Administrator.

O site, os bots e a API utilizam o mesmo armazenamento Django. A instalação local utiliza SQLite por predefinição; PostgreSQL pode ser configurado separadamente. Esta versão ainda não inclui OCR de rótulos nem criação automática de registos a partir de fotografias.

## Bot Telegram

O bot Telegram permite pesquisar o inventário em modo apenas de leitura. Em conversas privadas aceita nomes, fórmulas, números CAS, fornecedores, referências de catálogo e códigos de barras. Mostra embalagens disponíveis, localizações, ligações FDS e botões paginados quando existem vários resultados. Ignora grupos. É possível configurar uma lista de utilizadores Telegram autorizados.

A pesquisa por voz é opcional e requer a instalação e ativação do modelo local. Suporta português e inglês; os áudios têm o limite de 30 segundos e 5 MB. As páginas de resultados expiram após uma hora ou o reinício do processo. Execute apenas um processo de long polling por token.

## Bot WhatsApp — versão de teste

A integração utiliza a WhatsApp Cloud API da Meta com o número de teste da aplicação de desenvolvimento. Responde a mensagens recebidas de texto e áudio, pesquisa o stock disponível e apresenta listas interativas quando há vários resultados. Não altera o inventário, não envia campanhas e não inicia conversas por conta própria. Só podem ser usados destinatários adicionados e verificados na configuração de teste da Meta. A utilização em produção exige concluir o processo de ativação da Meta e configurar um número e credenciais de produção. A Meta limita respostas livres à janela de atendimento ao cliente; mensagens iniciadas pela empresa fora dessa janela exigem modelos aprovados. Consulte a [visão geral da Cloud API](https://developers.facebook.com/documentation/business-messaging/whatsapp/overview) e a [documentação de modelos](https://developers.facebook.com/docs/whatsapp/api/messages/message-templates/).

O webhook tem de estar acessível à Meta e configurado com o token de verificação e o segredo da aplicação correspondentes. As assinaturas dos pedidos recebidos são verificadas e os IDs duplicados são ignorados. A pesquisa por voz é opcional: requer o modelo local, suporta português e inglês e limita o áudio a 30 segundos e 5 MB. As pesquisas de texto aceitam 2–200 caracteres; as páginas expiram após uma hora ou o reinício do webhook. A lista opcional de remetentes pode restringir ainda mais o acesso.

## Origem e data do inventário

Os dados importados vieram do ficheiro SharePoint **`2026 Todos labs TEMA.xlsx`**. Os requisitos da base de dados registam que o ficheiro de origem foi consultado em **21 de setembro de 2026**. O lote atualmente registado na base de dados foi importado em **16 de novembro de 2026 às 15:19 (hora de Lisboa)**: 1.225 linhas importadas e 69 ignoradas. O livro contém uma folha de inventário de gases de agosto de 2026; o importador exclui a fotografia antiga de abril de 2026 e uma folha de impressão do armário de vapores.

O ficheiro de origem não está guardado neste repositório. `inventory/data/inventory_export_template.xlsx` é o modelo local de exportação XLSX, não o ficheiro de origem. A base de dados guarda o nome do ficheiro, a data de importação, o checksum e a contagem de linhas. Não regista separadamente a data de publicação ou de modificação do Excel; por isso, a data de consulta e a data de importação acima são factos distintos.

O identificador da versão Git é `v0.0.1`.
