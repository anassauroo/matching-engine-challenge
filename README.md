# Matching Engine — etapa 1

Base em Python para inserir ordens limit de um único ativo e visualizar cada
ordem em duas colunas, com identificadores sequenciais. Compras aparecem do
maior para o menor preço; vendas, do menor para o maior. Empates seguem a chegada.
Entradas inválidas exibem um erro e preservam o livro.

Requer Python 3.10 ou superior, sem dependências externas. Na pasta do repositório:

```powershell
python -m matching_engine
```

Comandos disponíveis:

```text
limit buy 10 100
limit buy 11 50
limit buy 10 200
limit sell 20 100
limit sell 19 80
print book
help
exit
```

A confirmação inclui o identificador: `Order created: buy 100 @ 10.00 id 1`.
Preços usam ponto, são positivos e têm até duas casas decimais; notação científica,
vírgula, sinais e valores não finitos são rejeitados. Quantidades são inteiros
positivos. Espaços extras são aceitos e linhas vazias são ignoradas. `exit` ou
fim da entrada encerram o programa.

Execute os testes com:

```powershell
python -m unittest discover -s tests -v
```

## Estruturas e limitações

`order.py` define uma dataclass imutável e converte preços com `Decimal` para
inteiros em centavos, sem usar float. `book.py` mantém duas listas em memória;
inserções são O(1) e a consulta ordenada custa O(n log n) por lado. É uma escolha
simples para esta etapa, sem otimização para grande volume. Identificador e
sequência de chegada avançam juntos porque só há inserções. `cli.py` valida
os comandos antes de inserir as ordens.

O livro começa vazio a cada execução; não há persistência. Todas as ordens limit
válidas ficam no livro, inclusive compras e vendas com preços compatíveis.
Esse estado é intermediário: o matching será implementado na próxima etapa.
Esta entrega não inclui trades, ordens market ou pegged, cancelamento, alteração,
API, interface gráfica ou infraestrutura de nuvem.

O PDF descreve o projeto completo; esta entrega cobre somente a primeira etapa.
