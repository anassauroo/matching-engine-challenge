"""Comandos de terminal para ordens limit com matching."""

import re
import sys
from typing import TextIO

from .book import OrderBook
from .order import format_price, parse_price


HELP = """Comandos:
  limit buy <price> <qty>
  limit sell <price> <qty>
  print book
  help
  exit
Preço: positivo, com ponto e até duas casas decimais (ex.: 10.50).
Quantidade: inteira positiva. Ordens limit compatíveis geram trades.
Cada trade usa o preço da ordem que já estava no livro."""


def execute(line: str, book: OrderBook, output: TextIO) -> bool:
    """Processa uma linha; retorna False apenas quando recebe exit válido."""
    tokens = line.split()
    if not tokens:
        return True
    try:
        if tokens == ["exit"]:
            return False
        if tokens == ["help"]:
            print(HELP, file=output)
        elif tokens == ["print", "book"]:
            print(book.render(), file=output)
        elif tokens[0] == "limit":
            if len(tokens) != 4:
                raise ValueError("Use: limit buy|sell <price> <qty>.")
            side, price_text, quantity_text = tokens[1:]
            price_cents = parse_price(price_text)
            if not re.fullmatch(r"[0-9]+", quantity_text):
                raise ValueError("Quantidade deve ser inteira positiva.")
            quantity = int(quantity_text)
            order, trades = book.add_limit(side, price_cents, quantity)
            print(f"Order created: {order.side} {order.quantity} @ {format_price(order.price_cents)} id {order.id}", file=output)
            for trade in trades:
                print(f"Trade, price: {format_price(trade.price_cents)}, qty: {trade.quantity}", file=output)
        else:
            raise ValueError("Comando desconhecido ou argumentos incorretos. Digite help.")
    except ValueError as error:
        print(f"Erro: {error}", file=output)
    return True


def main() -> None:
    book = OrderBook()
    interactive = sys.stdin.isatty()
    if interactive:
        print("Livro de ofertas — digite help para ver os comandos.")
    try:
        while True:
            if interactive:
                print(">>> ", end="", flush=True)
            line = sys.stdin.readline()
            if not line or not execute(line, book, sys.stdout):
                break
    except KeyboardInterrupt:
        print()
