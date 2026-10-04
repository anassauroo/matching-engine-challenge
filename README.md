# Matching Engine — etapa 2

Livro de ofertas de um único ativo em Python, com ordens limit e matching por
prioridade de preço e chegada. Compras consomem as vendas mais baratas; vendas
consomem as compras mais caras. No mesmo preço, a ordem mais antiga executa primeiro.
Cada ordem tem um identificador sequencial.

Requer Python 3.10 ou superior, sem dependências externas. Na pasta do repositório:

```powershell
python -m matching_engine
```

Comandos: `limit buy <price> <qty>`, `limit sell <price> <qty>`, `print book`,
`help` e `exit`. Espaços extras são aceitos e linhas vazias são ignoradas.
`exit` ou fim da entrada encerram o programa.

Preços são positivos, com ponto e até duas casas decimais. Quantidades são
inteiros positivos. Notação científica, vírgula, sinais e valores não finitos
são rejeitados. Entradas inválidas preservam o livro e os identificadores.

## Matching e exemplo

Ordens limit compatíveis são executadas, em vez de ignoradas: uma compra pode
pagar até seu limite; uma venda pode receber a partir de seu limite. Cada trade
usa o preço da ordem que **já estava no livro**, permitindo melhoria de preço
para a ordem recebida. Há uma linha de saída por par de ordens executado.

```text
limit sell 10 30
limit sell 11 40
limit buy 11 100
print book
```

A compra recebe ID 3 e gera:

```text
Order created: buy 100 @ 11.00 id 3
Trade, price: 10.00, qty: 30
Trade, price: 11.00, qty: 40
```

O livro mantém somente a compra restante de 30 unidades a 11.00, com ID 3.
A confirmação mostra a quantidade original recebida; o livro mostra o saldo.
Ordens totalmente preenchidas são removidas. Preenchimentos parciais preservam
ID, preço e sequência de chegada. Ordens sem contraparte compatível ficam no livro.

## Testes e estruturas

```powershell
python -m unittest discover -s tests -v
```

`order.py` define dataclasses imutáveis para ordens e trades. Preços são inteiros
em centavos, convertidos com `Decimal`, sem passar por float. `book.py` mantém
duas listas e ordena o lado oposto a cada inserção para executar o matching.
A consulta também ordena cada lado. O custo é O(n log n) por inserção/consulta,
com espaço O(n): uma escolha simples para esta etapa, sem otimização para grande
volume. Saldos são representados por novas instâncias, preservando a chegada.
`cli.py` valida os comandos e exibe confirmações, trades e o livro em duas colunas.

## Limitações

Tudo fica em memória; o livro e os IDs reiniciam a cada execução. Os trades são
retornados pela operação e exibidos, sem histórico persistente. Ainda não há
ordens market ou pegged, cancelamento, alteração, API ou interface gráfica.
O PDF descreve o projeto completo; esta entrega avança somente o matching de
ordens limit, substituindo o comportamento intermediário da primeira etapa.
