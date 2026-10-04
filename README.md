# Matching Engine Challenge — Python

Simulador de cruzamento de ordens de um único ativo, inteiramente em memória.
Implementa os requisitos funcionais do PDF: ordens **limit**, **market** e
**pegged**, prioridade por preço e chegada, preenchimentos parciais,
cancelamento, alteração e visualização individual das ordens em duas colunas.

## Executar

Requer **Python 3.10 ou superior**. Usa somente a biblioteca padrão, sem instalação
de pacotes. Abra um terminal na pasta `matching-engine-challenge` e execute:

```powershell
python -m matching_engine
```

Digite um comando por linha. `help` mostra a ajuda; `exit`, fim da entrada ou
Ctrl+C encerram o programa. Cada execução começa com livro vazio e IDs a partir
de 1. Também é possível enviar comandos por um pipe ou redirecionar a entrada.

## Comandos

| Comando | Comportamento |
| --- | --- |
| `limit buy <price> <qty>` | Compra até o preço informado; guarda o saldo |
| `limit sell <price> <qty>` | Vende a partir do preço informado; guarda o saldo |
| `market buy <qty>` | Compra imediatamente nas melhores vendas disponíveis |
| `market sell <qty>` | Vende imediatamente nas melhores compras disponíveis |
| `peg bid buy <qty>` | Compra acompanhando o melhor preço limit de compra |
| `peg offer sell <qty>` | Venda acompanhando o melhor preço limit de venda |
| `peg bid sell <qty>` / `peg offer buy <qty>` | Permite usar a referência do lado oposto; pode gerar trades imediatamente |
| `cancel order <id>` | Retira a ordem e seu saldo do livro |
| `amend order <id> price <price>` | Altera o preço de uma ordem limit |
| `amend order <id> qty <qty>` | Substitui a quantidade restante de uma limit ou pegged |
| `amend order <id> price <price> qty <qty>` | Altera preço e quantidade juntos; aceita os campos na ordem inversa |
| `print book` | Exibe cada ordem com quantidade restante, preço e ID |
| `help` | Lista os comandos |
| `exit` | Encerra a sessão |

Os comandos são escritos em minúsculas. Preços devem ser positivos e finitos,
com ponto e até duas casas decimais: `10`, `10.5`, `10.50` e `.50` são válidos.
Vírgula, sinais, notação científica e mais de duas casas (inclusive `10.000`)
são rejeitados. Quantidades e IDs são inteiros positivos.

Linhas vazias são ignoradas e espaços extras são aceitos. Comandos desconhecidos,
argumentos ausentes/extras, campos repetidos e IDs não disponíveis geram `Erro:`
sem encerrar a sessão, alterar o livro ou consumir IDs/sequências.

## Regras de matching

- Compras têm prioridade pelo maior preço; vendas, pelo menor. No mesmo preço,
  executa primeiro quem tem a sequência de chegada mais antiga.
- Uma compra cruza com uma venda quando seu preço é maior ou igual ao da venda.
  Ordens limit compatíveis são **preenchidas**, opção permitida pelo PDF: assim
  a liquidez disponível é utilizada imediatamente e o livro termina sem cruzamentos.
- O preço do trade é o da ordem com a sequência de chegada mais antiga no par.
  No matching limit comum, é a ordem que já estava no livro. Para market,
  é sempre o preço da contraparte no livro.
- A quantidade executada é o menor saldo do par. Ordens preenchidas são removidas;
  preenchimentos parciais mantêm ID e chegada. Uma limit não executada fica no livro.
- Market não fica no livro: o saldo sem liquidez é descartado, com a mensagem
  `Unfilled quantity cancelled: <qty>`. Livro vazio é um caso válido.
- As confirmações mostram a quantidade recebida; `print book` mostra a restante.
  Todas as ordens válidas, inclusive market sem execução, recebem IDs únicos.
- Internamente, cada trade identifica as duas ordens. Na saída, execuções
  consecutivas ao mesmo preço são somadas, seguindo o exemplo do PDF:
  `Trade, price: 20.00, qty: 150`.

## Alteração e cancelamento

Uma alteração mantém o ID e o lado. Mudança de preço ou aumento de quantidade
atribui nova sequência de chegada, colocando a ordem atrás das demais no mesmo
preço. Redução de quantidade ou alteração sem mudança efetiva preserva a prioridade.
`qty` substitui o **saldo atual**, sem somar à quantidade original já negociada.
Quantidade zero é rejeitada; para remover a ordem, use `cancel order`.

Uma alteração pode gerar trades imediatamente. O cancelamento retira toda a
quantidade restante e confirma `Order cancelled`. Ordens já preenchidas,
canceladas ou market não podem ser alteradas/canceladas. Não há reutilização de IDs.

## Ordens pegged e decisões adotadas

O PDF especifica o acompanhamento de bid/offer e a prioridade do exemplo, mas
não define referência circular, ausência de referência ou alteração de quantidade.
Esta implementação usa as seguintes regras explícitas:

- **Bid** é o maior preço das ordens limit de compra; **offer**, o menor preço das
  ordens limit de venda. Pegged não define a referência, evitando que uma ordem
  sustente seu próprio preço ou crie um ciclo com outra pegged.
- Sem uma limit de referência, a pegged permanece no livro como **inativa**, sem
  participar do matching. É reativada quando a referência reaparece; pode ser
  cancelada ou ter a quantidade alterada enquanto estiver inativa.
- Os preços são recalculados após inserção, cancelamento, alteração e cada
  preenchimento. Isso também atualiza pegged após consumo completo da referência.
  A atualização ocorre **antes de escolher o próximo par para matching**.
- A atualização automática preserva a sequência de chegada original. Assim,
  uma pegged antiga fica à frente de uma nova limit no mesmo preço, conforme o PDF.
  Quando duas ordens já existentes cruzam após atualização, vale a regra de preço
  da sequência mais antiga descrita acima.
- Pegged participa de trades como limit no preço atual. A referência e o lado
  são independentes: as quatro combinações bid/offer e buy/sell são aceitas.
- Alteração manual de preço de pegged é rejeitada, pois o preço é automático.
  Alteração de quantidade segue a mesma regra de prioridade das limit.

## Exemplos

### Market e preenchimento parcial — exemplo do PDF

Em uma sessão nova:

```text
limit buy 10 100
limit sell 20 100
limit sell 20 200
market buy 150
market buy 200
market sell 200
print book
```

Os trades são `150 @ 20.00`, `150 @ 20.00` e `100 @ 10.00`. A segunda market
descarta 50 unidades e a terceira descarta 100. O livro termina vazio.

### Pegged, alteração e cancelamento

Em outra sessão nova:

```text
limit buy 10 200
limit buy 9.99 100
limit sell 10.50 100
peg bid buy 150
limit buy 10.10 300
print book
amend order 5 price 9.98 qty 250
print book
cancel order 1
print book
exit
```

No primeiro `print book`, as compras são:

```text
150 @ 10.10 id 4 peg bid
300 @ 10.10 id 5
200 @ 10.00 id 1
100 @ 9.99 id 2
```

A venda é `100 @ 10.50 id 3`. Após a alteração da ordem 5, a pegged acompanha
10.00; após cancelar a ordem 1, acompanha 9.99. Para testar offer, use
`peg offer sell <qty>` e insira/altere/cancele as vendas limit de referência.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes cobrem preço/tempo nos dois lados, conversão exata de preços, IDs,
matching limit e market, preenchimentos parciais, livro vazio, cancelamento,
alterações e perda/preservação de prioridade, pegged bid/offer, ausência e
consumo da referência, reativação, comandos inválidos e encerramento.
Uma sequência determinística de 400 operações mistas verifica conservação de
quantidades, referências atualizadas e ausência de cruzamentos ao final de cada comando.

## Organização e limites

- `matching_engine/order.py`: dataclasses imutáveis `Order` e `Trade`, conversão
  com `Decimal` e preços armazenados como inteiros em centavos, sem usar float.
- `matching_engine/book.py`: dicionário de ordens por ID, prioridades, matching,
  cancelamento, alteração, referências pegged e visualização.
- `matching_engine/cli.py`: validação dos comandos e mensagens do terminal.
- `tests/`: testes com `unittest`, sem ferramentas externas.

O dicionário facilita a busca por ID; as consultas por lado ordenam as ordens.
A visualização custa O(n log n). Cada seleção/reprecificação custa até O(n log n);
um comando com k trades custa O((k + 1) n log n), podendo chegar a O(n² log n).
O espaço é O(n + k), incluindo os trades retornados pelo comando. São estruturas
simples para o exercício, sem otimização para grande volume ou baixa latência.
O laço de matching termina porque cada trade remove pelo menos uma ordem.

Não há armazenamento persistente de ordens/trades, múltiplos ativos, concorrência,
API, interface gráfica, taxas ou infraestrutura de nuvem. Essas funcionalidades
não fazem parte do exercício. O histórico Git registra as etapas do desenvolvimento;
a publicação no GitHub é uma ação separada da implementação local.
