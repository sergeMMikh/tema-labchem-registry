# Fotografias de rótulos de reagentes

Envie uma fotografia nítida do rótulo de um frasco ao bot Telegram ou WhatsApp. O bot lê o nome, número CAS, referência de catálogo e fabricante com a visão da OpenAI. Depois pesquisa o inventário TEMA. A correspondência por CAS tem prioridade, seguida da referência exata e de um nome exato sem ambiguidade. Se houver correspondência, mostra o reagente, embalagens, quantidades e localizações; não consulta o site Sigma-Aldrich.

Se o reagente não existir no inventário, o bot pesquisa o catálogo Sigma-Aldrich. Quando o site responde, apresenta o título e a descrição da página, além da ligação direta. Se o acesso direto falhar, uma pesquisa web da OpenAI limitada às páginas oficiais Sigma-Aldrich tenta obter um resumo com fonte. Se ambos os métodos falharem, o bot informa o utilizador e fornece a ligação. Um rótulo ilegível exige uma imagem mais clara; o bot não inventa números CAS ou detalhes de produto.

Se a pesquisa por fotografia não encontrar o reagente, escreva **Adicionar**, **Add** ou **Добавь** para abrir a confirmação. **Sim** abre a lista de locais de armazenamento ativos. A escolha cria o reagente com uma embalagem no estado **Pendente de revisão**. O bot guarda os dados reconhecidos do rótulo e a ligação oficial da Sigma, quando disponível. A quantidade, o lote e a validade ficam em branco. **Não** cancela a operação.

## Registar um reagente por texto

Comece com uma pesquisa por texto. Se o reagente estiver ausente da base de dados, o bot indica o resultado. Escreva **Adicionar**, **Add** ou **Добавь** para abrir o formulário em português, inglês ou russo, respetivamente. Indique o nome e escolha um local de armazenamento. Preencha os restantes dados do reagente e da embalagem ou escreva **Saltar** nos campos opcionais que quiser deixar em branco. Introduza as datas como DD/MM/AAAA.

O bot mostra a ficha preenchida com as opções **Confirmar**, **Cancelar** e **Alterar**. Escolha **Alterar** e indique o campo pelo número ou pelo nome. Depois de cada alteração, o bot mostra a ficha atualizada e as três opções. **Confirmar** guarda o reagente e uma embalagem no local escolhido e marca a embalagem como **Pendente de revisão**. O rascunho expira após uma hora de inatividade ou após o reinício do processo.

## Configuração e limites

Defina `OPEN_AI_KEY` no `.env` local; `OPEN_AI_VISION_MODEL` (predefinição `gpt-4.1-mini`) e `OPEN_AI_SEARCH_MODEL` (predefinição `gpt-5.4-mini`) são opcionais. Reinicie o processo Telegram e o serviço web WhatsApp após alterar o ambiente. O Telegram recebe fotografias e o WhatsApp recebe imagens através do webhook configurado. O tamanho máximo de transferência é 10 MB. As imagens são reduzidas a 1800 píxeis, convertidas para JPEG e enviadas à OpenAI para reconhecimento; não envie rótulos confidenciais se este processamento externo não for aceitável. A utilização da API OpenAI para imagem e pesquisa web pode ter custos. `TELEGRAM_SAVE_USER_IDS` e `WHATSAPP_SAVE_USER_IDS` vazios permitem guardar a todos os utilizadores com acesso aos bots; para restringir mais tarde, defina IDs Telegram ou números WhatsApp separados por vírgulas. Mantêm-se as restrições do número de teste WhatsApp.

As páginas Sigma-Aldrich podem estar indisponíveis ou mudar de estrutura; nesse caso é fornecida apenas a ligação, sem afirmar um resultado de catálogo verificado. A identificação depende da legibilidade do rótulo e deve ser confirmada no frasco antes de utilização em laboratório.

Referências: [imagens na API OpenAI](https://platform.openai.com/docs/guides/images-vision) · [catálogo Sigma-Aldrich](https://www.sigmaaldrich.com/PT/en/search/acetone?focus=products&term=acetone&type=product).
