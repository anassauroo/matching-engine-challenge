# Matching Engine Challenge

Simulador em Python do cruzamento de ordens de um único ativo, com ordens
limit, market e pegged, prioridade por preço e chegada, preenchimentos parciais,
cancelamento, alteração e visualização do livro. Todos os dados ficam em memória.

## Execução

Requer **Python 3.10 ou superior** e usa somente a biblioteca padrão.
Na pasta `matching-engine-challenge`, execute:

```powershell
python -m matching_engine
```

Digite um comando por linha. `help` mostra a ajuda; `exit`, fim da entrada ou
Ctrl+C encerram a sessão. O livro começa vazio e os IDs reiniciam a cada execução.

## Comandos

| Comando | Descrição |
| --- | --- |
| `limit buy <price> <qty>` | Insere uma compra limit e guarda o saldo não executado |
| `limit sell <price> <qty>` | Insere uma venda limit e guarda o saldo não executado |
| `market buy <qty>` | Compra imediatamente na liquidez disponível |
| `market sell <qty>` | Vende imediatamente na liquidez disponível |
| `peg bid buy <qty>` | Compra acompanhando o melhor preço limit de compra |
| `peg bid sell <qty>` | Venda acompanhando o melhor preço limit de compra |
| `peg offer buy <qty>` | Compra acompanhando o melhor preço limit de venda |
| `peg offer sell <qty>` | Venda acompanhando o melhor preço limit de venda |
| `cancel order <id>` | Remove a ordem e seu saldo |
| `amend order <id> price <price>` | Altera o preço de uma limit |
| `amend order <id> qty <qty>` | Substitui a quantidade restante |
| `amend order <id> price <price> qty <qty>` | Altera ambos; aceita os campos na ordem inversa |
| `print book` | Exibe compras e vendas, com preço, saldo e ID |
| `help` / `exit` | Exibe a ajuda / encerra a sessão |

Os comandos usam minúsculas. Preços são positivos e finitos, com ponto e até duas
casas decimais; quantidades e IDs são inteiros positivos. Entradas inválidas
exibem um erro sem modificar o livro. Linhas vazias e espaços extras são aceitos.

## Exemplo

Em uma sessão nova:

```text
limit sell 10 30
limit sell 11 40
limit buy 11 100
print book
```

A compra gera `Trade, price: 10.00, qty: 30` e
`Trade, price: 11.00, qty: 40`. O livro mantém a compra restante de 30 unidades
a 11.00, com ID 3. Para alterá-la ou cancelá-la:

```text
amend order 3 qty 20
cancel order 3
```

## Regras e decisões técnicas

- **Matching:** compras priorizam o maior preço; vendas, o menor. Empates seguem
  a chegada. Limit compatíveis são executadas, opção permitida pelo enunciado,
  para aproveitar a liquidez disponível imediatamente. Preenchimentos parciais
  preservam ID e chegada; ordens preenchidas são removidas.
- **Preço dos trades:** para limit/pegged, usa-se o preço da ordem com a sequência
  de chegada mais antiga no par; para market, o da contraparte no livro.
  Execuções consecutivas ao mesmo preço são agrupadas na saída, como no PDF.
- **Market:** o saldo sem liquidez é descartado e informado no terminal; a ordem
  nunca fica no livro.
- **Alteração:** mantém o ID e o lado. Mudança de preço ou aumento de quantidade
  perde prioridade; redução ou mudança sem efeito preserva a chegada. `qty`
  substitui o saldo atual. Alterações podem gerar trades imediatamente.
- **Pegged:** bid/offer considera apenas ordens limit, evitando referências
  circulares. Sem referência, a ordem fica inativa e é reativada quando ela
  reaparece. O preço é atualizado antes do próximo matching, após cada mudança
  no livro, inclusive preenchimentos. Atualizações automáticas preservam a
  chegada, conforme o exemplo do PDF. As quatro combinações de referência e lado
  são aceitas. É possível alterar a quantidade, mas o preço é automático.
- **Cancelamento:** remove todo o saldo. Ordens inexistentes, preenchidas,
  canceladas ou market não podem ser alteradas/canceladas. IDs não são reutilizados
  durante a sessão. Quantidade zero é rejeitada; a remoção usa `cancel order`.

### Preço após atualização de pegged

O PDF não define o preço de execução nesse caso. Aqui, preservar a chegada da
pegged também permite que seu preço atualizado determine o trade quando ela é
a mais antiga do par. É uma convenção do simulador; não pretende representar
uma regra universal de exchanges.

Em uma sessão nova:

```text
limit buy 10 100
peg bid buy 5
limit sell 10.50 10
limit buy 11 5
```

A pegged (ID 2) acompanha 11.00 e executa 5 unidades contra a venda (ID 3) a
**11.00**, pois é mais antiga. As outras 5 unidades da venda executam contra a
nova compra (ID 4) a **10.50**, pois a venda é mais antiga nesse segundo par.
Ambos os preços respeitam os limites de compra e venda. Se a venda for inserida
antes da pegged, os dois trades ocorrem a 10.50. Os testes verificam esses
resultados e o caso simétrico com `peg offer sell`.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes cobrem prioridade, preços, IDs, matching, preenchimentos parciais,
cancelamento, alteração, referências pegged e entradas inválidas. Incluem os
exemplos do PDF e casos específicos de interação entre as funcionalidades.

## Estrutura e limitações

| Arquivo | Responsabilidade |
| --- | --- |
| `matching_engine/order.py` | Dataclasses imutáveis e conversão de preços |
| `matching_engine/book.py` | Livro, matching, cancelamento, alteração e pegged |
| `matching_engine/cli.py` | Comandos, validação e saída do terminal |
| `tests/` | Testes com `unittest` |

Preços são inteiros em centavos, convertidos com `Decimal`, sem passar por float.
O livro usa um dicionário por ID e ordena as ordens por lado ao consultar.
A visualização custa O(n log n); um comando com k trades custa
O((k + 1) n log n), com espaço O(n + k). A escolha privilegia simplicidade para
este exercício, sem otimização para grande volume ou baixa latência.

A aplicação opera com um único ativo, sem persistência ou concorrência.
Não inclui API, interface gráfica ou infraestrutura de nuvem.
