"""Interface de terminal da matching engine."""

from itertools import groupby
import re
import sys
from typing import TextIO

from .book import OrderBook
from .order import Trade, format_price, parse_price


HELP = """Comandos:
  limit buy|sell <price> <qty>
  market buy|sell <qty>
  peg bid|offer buy|sell <qty>
  cancel order <id>
  amend order <id> price <price>
  amend order <id> qty <qty>
  amend order <id> price <price> qty <qty>
  print book
  help
  exit
Preço: positivo, com ponto e até duas casas decimais (ex.: 10.50).
Quantidade: inteira positiva. Market descarta o saldo sem liquidez.
Pegged acompanha ordens limit; sem referência, fica inativa.
Alteração de preço ou aumento de quantidade perde prioridade.
Trades usam o preço da ordem com prioridade de chegada mais antiga."""


def parse_integer(text: str, name: str) -> int:
    if not re.fullmatch(r"[0-9]+", text):
        raise ValueError(f"{name} deve ser inteiro positivo.")
    value = int(text)
    if value <= 0:
        raise ValueError(f"{name} deve ser inteiro positivo.")
    return value


def print_trades(trades: list[Trade], output: TextIO) -> None:
    # Agrupa apenas execuções consecutivas ao mesmo preço, como no PDF.
    for price, executions in groupby(trades, key=lambda trade: trade.price_cents):
        quantity = sum(trade.quantity for trade in executions)
        print(f"Trade, price: {format_price(price)}, qty: {quantity}", file=output)


def execute(line: str, book: OrderBook, output: TextIO) -> bool:
    """Valida toda a linha antes de modificar o livro; False encerra a sessão."""
    tokens = line.split()
    if not tokens:
        return True
    try:
        trades: list[Trade] = []
        if tokens == ["exit"]:
            return False
        if tokens == ["help"]:
            print(HELP, file=output)
        elif tokens == ["print", "book"]:
            print(book.render(), file=output)
        elif tokens[0] == "limit":
            if len(tokens) != 4:
                raise ValueError("Use: limit buy|sell <price> <qty>.")
            order, trades = book.add_limit(tokens[1], parse_price(tokens[2]),
                                           parse_integer(tokens[3], "Quantidade"))
            print(f"Order created: {order.side} {order.quantity} @ {format_price(order.price_cents)} id {order.id}", file=output)
        elif tokens[0] == "market":
            if len(tokens) != 3:
                raise ValueError("Use: market buy|sell <qty>.")
            order, trades, unfilled = book.add_market(tokens[1], parse_integer(tokens[2], "Quantidade"))
            print(f"Order created: market {order.side} {order.quantity} id {order.id}", file=output)
            print_trades(trades, output)
            if unfilled:
                print(f"Unfilled quantity cancelled: {unfilled}", file=output)
            return True
        elif tokens[0] == "peg":
            if len(tokens) != 4:
                raise ValueError("Use: peg bid|offer buy|sell <qty>.")
            order, trades = book.add_pegged(tokens[1], tokens[2], parse_integer(tokens[3], "Quantidade"))
            price = format_price(order.price_cents) if order.price_cents is not None else "inativa"
            print(f"Order created: peg {order.peg_reference} {order.side} {order.quantity} @ {price} id {order.id}", file=output)
        elif tokens[0] == "cancel":
            if len(tokens) != 3 or tokens[1] != "order":
                raise ValueError("Use: cancel order <id>.")
            trades = book.cancel(parse_integer(tokens[2], "Identificador"))
            print("Order cancelled", file=output)
        elif tokens[0] == "amend":
            if len(tokens) not in (5, 7) or tokens[1] != "order":
                raise ValueError("Use: amend order <id> price <price> e/ou qty <qty>.")
            order_id = parse_integer(tokens[2], "Identificador")
            changes: dict[str, int] = {}
            for index in range(3, len(tokens), 2):
                field, value = tokens[index:index + 2]
                if field not in ("price", "qty") or field in changes:
                    raise ValueError("Campos permitidos: price e qty, sem repetição.")
                changes[field] = parse_price(value) if field == "price" else parse_integer(value, "Quantidade")
            order, trades = book.amend(order_id, price_cents=changes.get("price"), quantity=changes.get("qty"))
            print(f"Order amended: id {order.id}", file=output)
        else:
            raise ValueError("Comando desconhecido ou argumentos incorretos. Digite help.")
        print_trades(trades, output)
    except ValueError as error:
        print(f"Erro: {error}", file=output)
    return True


def main() -> None:
    book = OrderBook()
    interactive = sys.stdin.isatty()
    if interactive:
        print("Matching engine — digite help para ver os comandos.")
    try:
        while True:
            if interactive:
                print(">>> ", end="", flush=True)
            line = sys.stdin.readline()
            if not line or not execute(line, book, sys.stdout):
                break
    except KeyboardInterrupt:
        print()
