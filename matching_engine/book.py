"""Livro simples: listas por lado e ordenação ao consultar."""

from itertools import zip_longest
from dataclasses import replace

from .order import LimitOrder, Trade, format_price


class OrderBook:
    def __init__(self) -> None:
        self._buys: list[LimitOrder] = []
        self._sells: list[LimitOrder] = []
        self._next_id = 1

    def add_limit(self, side: str, price_cents: int, quantity: int) -> tuple[LimitOrder, list[Trade]]:
        """Cruza uma ordem válida e guarda apenas o saldo não executado.

        Retorna a ordem recebida (quantidade original) e seus trades.
        Cada execução usa o preço da ordem que já estava no livro.
        """
        if side not in ("buy", "sell"):
            raise ValueError("Lado deve ser buy ou sell.")
        if type(price_cents) is not int or price_cents <= 0:
            raise ValueError("Preço em centavos deve ser inteiro positivo.")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Quantidade deve ser inteira positiva.")
        order = LimitOrder(self._next_id, side, price_cents, quantity, self._next_id)
        opposite = self._sells if side == "buy" else self._buys
        candidates = self.sell_orders() if side == "buy" else self.buy_orders()
        remaining = quantity
        trades: list[Trade] = []
        balances: dict[int, int] = {}
        for resting in candidates:
            if remaining == 0:
                break
            if side == "buy" and resting.price_cents > price_cents:
                break
            if side == "sell" and resting.price_cents < price_cents:
                break
            executed = min(remaining, resting.quantity)
            buy_id, sell_id = (order.id, resting.id) if side == "buy" else (resting.id, order.id)
            trades.append(Trade(resting.price_cents, executed, buy_id, sell_id))
            remaining -= executed
            balances[resting.id] = resting.quantity - executed

        opposite[:] = [replace(resting, quantity=balances.get(resting.id, resting.quantity))
                       for resting in opposite
                       if balances.get(resting.id, resting.quantity) > 0]
        if remaining:
            (self._buys if side == "buy" else self._sells).append(replace(order, quantity=remaining))
        self._next_id += 1
        return order, trades

    def buy_orders(self) -> list[LimitOrder]:
        return sorted(self._buys, key=lambda order: (-order.price_cents, order.arrival_sequence))

    def sell_orders(self) -> list[LimitOrder]:
        return sorted(self._sells, key=lambda order: (order.price_cents, order.arrival_sequence))

    def render(self) -> str:
        def describe(order: LimitOrder) -> str:
            return f"{order.quantity} @ {format_price(order.price_cents)} id {order.id}"

        buys = [describe(order) for order in self.buy_orders()]
        sells = [describe(order) for order in self.sell_orders()]
        width = max(len("Ordens de Compra"), *(len(row) for row in buys)) if buys else len("Ordens de Compra")
        lines = [f"{'Ordens de Compra':<{width}} | Ordens de Venda", f"{'-' * width}-|-----------------"]
        for buy, sell in zip_longest(buys, sells, fillvalue=""):
            lines.append(f"{buy:<{width}} | {sell}")
        return "\n".join(lines)
