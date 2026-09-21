# Requisitos de conceção da base de dados

[English](DATABASE_REQUIREMENTS.md) · **Português**

Este documento define os requisitos de conceção e formatação de dados do LabChem Registry. Baseia-se na análise do ficheiro [2026 Todos labs TEMA.xlsx](https://uapt33090-my.sharepoint.com/:x:/g/personal/lrocha_ua_pt/IQAWNeX4mo45S6fXA5kON1MQAeEI0trkb8UDvVU3lHDq-_Q?e=ttVMRJ), consultado em 21 de setembro de 2026, e nos requisitos do projeto.

## 1. Observações sobre o ficheiro de origem

O ficheiro contém dez folhas com reagentes gerais, garrafas de gás, laboratórios individuais, armários e itens que não foram encontrados. Os dados não deverão ser copiados diretamente para uma tabela de produção porque:

- campos equivalentes têm nomes diferentes, como `Name`/`Nome`, `Supplier`, `Storage`, `Localização`, `Link to SDS` e `Link to MSDS`;
- algumas folhas contêm várias tabelas independentes e cabeçalhos repetidos;
- títulos, legendas, datas de levantamento e notas operacionais aparecem entre as linhas de dados;
- as datas são números do Excel, texto formatado ou `?`;
- as quantidades combinam números, unidades, contagens e comentários no mesmo valor;
- o estado, a validade, a pureza e os comentários aparecem por vezes no nome do reagente;
- as localizações são texto livre e nem sempre separam laboratório, armário e prateleira;
- o mesmo produto químico pode existir em várias embalagens físicas, mas estas não têm um identificador comum estável;
- os valores CAS contêm espaços iniciais, valores em falta e pelo menos um valor que aparenta ser outro identificador;
- as garrafas de gás exigem atributos que não são usados de forma consistente nos restantes reagentes.

O ficheiro é, por isso, uma fonte de migração e não o modelo da base de dados de destino.

## 2. Princípios gerais

1. Utilizar PostgreSQL como base de dados principal na rede interna da instituição.
2. Criar um registo por embalagem física ou garrafa de gás.
3. Separar a identidade química da unidade física de inventário.
4. Normalizar laboratórios, armários e prateleiras, em vez de guardar a localização completa como texto livre.
5. Utilizar identificadores internos imutáveis; nomes, números CAS e linhas da folha de cálculo não podem ser chaves primárias.
6. Preservar os valores originais importados para rastreabilidade e guardar separadamente os valores normalizados.
7. Não eliminar fisicamente registos de inventário ou de auditoria nos fluxos normais da aplicação.
8. Guardar timestamps em UTC e apresentá-los no fuso horário do utilizador.
9. Guardar estados e unidades controlados como códigos, e não como texto traduzido.
10. Aplicar as regras de acesso no backend/API, e não apenas na interface.

## 3. Modelo de dados obrigatório

### 3.1 Produto químico

Representa uma identidade química partilhada por uma ou mais unidades de inventário.

| Campo | Tipo | Requisito |
|---|---|---|
| `id` | UUID | Chave primária gerada pelo sistema |
| `preferred_name` | texto | Obrigatório, sem espaços exteriores |
| `formula` | texto | Opcional; preservar maiúsculas e notação química |
| `cas_number` | texto | Opcional; normalizado como `N{2,7}-NN-N` e com dígito de controlo validado |
| `physical_state` | código | Opcional: sólido, líquido, gás, mistura, outro ou desconhecido |
| `notes` | texto | Opcional; não substitui campos estruturados |

Os nomes alternativos deverão ser guardados numa tabela `chemical_alias`. A ausência de número CAS é permitida. O CAS não deverá ser considerado universalmente único, devido a misturas e exceções de qualidade; possíveis duplicados deverão ser revistos durante a importação.

### 3.2 Unidade de inventário

Representa uma embalagem, recipiente ou garrafa física.

| Campo | Tipo | Requisito |
|---|---|---|
| `id` | UUID | Chave primária e futuro valor do código QR |
| `chemical_id` | UUID | Chave estrangeira obrigatória para `chemical` |
| `manufacturer_id` | UUID | Chave estrangeira opcional |
| `catalog_number` | texto | Opcional; guardado como texto |
| `lot_number` | texto | Opcional |
| `concentration_or_grade` | texto | Opcional |
| `nominal_quantity` | decimal | Opcional; deve ser positiva |
| `quantity_unit` | código | Obrigatório quando existe quantidade nominal |
| `container_count` | inteiro | Valor predefinido 1; positivo |
| `expiry_date` | data | Opcional; não inventar dia ou mês |
| `location_id` | UUID | Obrigatório enquanto a unidade estiver disponível |
| `responsible_user_id` | UUID | Chave estrangeira opcional |
| `status` | código | Obrigatório; predefinição `available` |
| `label_photo_id` | UUID | Referência opcional aos metadados da imagem |
| `notes` | texto | Opcional |
| `created_at`, `updated_at` | timestamp | Obrigatórios e geridos pelo sistema |

Os estados iniciais permitidos são `available`, `retired`, `not_found` e `pending_review`. Outros estados exigem uma migração explícita e um significado funcional documentado.

O controlo de consumo parcial e da quantidade restante não pertence ao âmbito da primeira versão. Valores como `Estimated quantity left` deverão ser preservados nos dados de origem da migração ou em notas, mas não deverão alimentar cálculos de stock atuais.

### 3.3 Extensão para garrafas de gás

Os dados específicos dos gases deverão ficar num registo `gas_cylinder`, associado numa relação de zero-ou-um para um com a unidade de inventário:

- referência da garrafa ou do fornecedor;
- mistura/composição do gás, quando a ficha química não for suficiente;
- indicador de necessidade de substituição;
- notas específicas da garrafa.

Uma garrafa de gás continua a ser uma unidade de inventário e segue as mesmas regras de estado, localização e auditoria.

### 3.4 Hierarquia de localizações

As localizações deverão utilizar chaves estrangeiras explícitas:

```text
laboratório → armário/unidade de armazenamento → prateleira
```

- O laboratório tem um código institucional único, como `3.2.22`, e uma designação.
- Um armário pertence exatamente a um laboratório.
- Uma prateleira pertence exatamente a um armário.
- Os códigos são únicos dentro da localização hierarquicamente superior.
- Poderá existir uma localização temporária para importações `pending_review` ou `not_found`.
- Descrições como “armário de extração de vapores” são atributos da unidade de armazenamento, não texto do nome do reagente.

Não é necessário numerar posições individuais dentro de uma prateleira.

### 3.5 Fabricantes e documentos de segurança

Os fabricantes/fornecedores deverão ser normalizados para evitar entidades duplicadas causadas por variantes ortográficas. O texto original deverá continuar disponível durante a importação.

As Fichas de Dados de Segurança deverão ser guardadas numa tabela `safety_document` com:

- identificador interno;
- associação ao produto químico ou à unidade de inventário;
- URL de origem ou referência do ficheiro gerido;
- idioma;
- data de revisão/entrada em vigor, quando conhecida;
- tipo de documento (`SDS` ou o antigo `MSDS`);
- timestamp de criação.

Não deverá ser guardado apenas o título de uma hiperligação sem o respetivo URL ou ficheiro.

### 3.6 Utilizadores e histórico de auditoria

O modelo deverá suportar os perfis `user`, `laboratory_manager` e `administrator`. Cada operação que altere o estado da base deverá criar um evento de auditoria apenas acrescentável, contendo:

- identificador do evento;
- identificador da unidade de inventário;
- identificador do utilizador ou de uma identidade própria de importação/serviço;
- tipo de evento;
- timestamp;
- valores estruturados anteriores e novos, quando aplicável;
- motivo ou comentário opcional.

Deverão ser auditados, pelo menos, a adição, a edição da ficha, a alteração da localização e o abate. O abate altera o estado e não elimina o registo.

### 3.7 Reconhecimento de rótulos

O resultado de OCR ou IA deverá ser inicialmente guardado como rascunho associado à imagem e aos metadados do reconhecimento. Deverá incluir valores extraídos, níveis de confiança quando disponíveis, versão do modelo/serviço e timestamp do processamento. Um rascunho só se torna dado de produção após confirmação ou correção pelo utilizador.

## 4. Regras de formatação dos dados

- Guardar texto em Unicode e remover espaços normais ou inquebráveis no início e no fim.
- Preservar acentos, maiúsculas e minúsculas das fórmulas químicas.
- Não acrescentar datas de validade, instruções de armazenamento ou comentários de estado ao nome.
- Guardar números CAS como texto, remover espaços exteriores, validar o formato e o dígito de controlo e encaminhar falhas para revisão.
- Guardar datas no formato ISO (`YYYY-MM-DD`); uma data desconhecida é `NULL`, nunca `?`.
- Quando apenas o ano ou o mês forem conhecidos, registar explicitamente a precisão sem inventar uma data completa.
- Separar a quantidade decimal da unidade controlada; valores como `2.5 L`, `10 g + 10 g` ou `30% | 50%` não deverão tornar-se valores calculáveis sem revisão.
- Utilizar ponto decimal internamente, independentemente do idioma da interface.
- Guardar referências de catálogo, lote, sala, armário, prateleira e garrafa como texto para preservar zeros iniciais e letras.
- Utilizar `NULL` para valores desconhecidos; strings vazias, traços e pontos de interrogação não são substitutos válidos.
- Colocar comentários operacionais em notas ou eventos de auditoria, não em campos de identidade.
- Tratar fotografias e documentos como objetos geridos; guardar metadados e referências na base de dados, e não ficheiros binários grandes, salvo decisão explícita da arquitetura de armazenamento.

## 5. Restrições e índices

A base de dados deverá aplicar chaves estrangeiras e restrições de validação. Deverá incluir, pelo menos, índices para:

- nome químico normalizado e nomes alternativos, incluindo pesquisa parcial;
- número CAS;
- fabricante e referência de catálogo;
- estado da unidade de inventário;
- laboratório, armário e prateleira;
- data de validade;
- eventos de auditoria por unidade e timestamp.

Os possíveis duplicados deverão ser identificados através da combinação de produto químico, fabricante, referência de catálogo, lote, localização e linha de origem. A deteção deverá gerar um aviso ou uma revisão; nunca deverá fundir silenciosamente embalagens físicas.

## 6. Requisitos de migração da folha de cálculo

1. Importar cada folha para uma área de staging antes de criar registos de produção.
2. Registar ficheiro, folha, linha, lote de importação e valores originais das células.
3. Detetar e excluir títulos, legendas, linhas vazias e cabeçalhos repetidos dos registos de inventário.
4. Mapear as variantes de colunas para o esquema canónico.
5. Dividir valores incorporados apenas quando a transformação for determinística; nos restantes casos, solicitar revisão.
6. Normalizar fornecedores, localizações, datas, unidades e números CAS.
7. Tratar as linhas “Não encontrei” como candidatas a `not_found`, não como inventário disponível.
8. Comparar as folhas de gases de abril e agosto de 2026 como levantamentos temporais; não importar ambas como garrafas independentes.
9. Produzir um relatório com linhas aceites, avisos, rejeições e possíveis duplicados.
10. Exigir aprovação humana antes de promover os dados de staging para produção.

## 7. Critérios mínimos de aceitação

O desenho da base de dados é aceitável quando:

- cada unidade física tem um identificador único e estável;
- cada unidade disponível aponta para laboratório, armário/unidade de armazenamento e prateleira;
- a pesquisa funciona por nome completo ou parcial, CAS, fabricante, referência de catálogo e laboratório;
- a pesquisa normal exclui unidades abatidas por predefinição;
- as mudanças de localização e os abates são integralmente auditáveis;
- datas, CAS, unidades e localizações inválidas não entram silenciosamente em produção;
- resultados de OCR e importações exigem confirmação;
- a interface web e os bots utilizam o mesmo backend e a mesma base de dados.

## 8. Fora do âmbito da primeira versão

- controlo de consumo parcial;
- cálculo em tempo real da quantidade restante;
- posições numeradas dentro de uma prateleira;
- impressão obrigatória de códigos QR.

O esquema deverá, contudo, permitir acrescentar códigos QR no futuro sem alterar os identificadores das unidades de inventário.
