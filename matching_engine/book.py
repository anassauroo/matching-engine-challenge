"""Livro em memória, matching e manutenção das referências pegged."""

from dataclasses import replace
from itertools import zip_longest

from .order import Order, Trade, format_price


def positive_integer(value: int, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} deve ser inteiro positivo.")


def validate_side(side: str) -> None:
    if side not in ("buy", "sell"):
        raise ValueError("Lado deve ser buy ou sell.")


class OrderBook:
    def __init__(self) -> None:
        self._orders: dict[int, Order] = {}
        self._next_id = 1
        self._next_sequence = 1

    def _sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def _create(self, side: str, price_cents: int | None, quantity: int,
                order_type: str, reference: str | None = None) -> Order:
        order = Order(self._next_id, side, price_cents, quantity,
                      self._sequence(), order_type, reference)
        self._next_id += 1
        return order

    def add_limit(self, side: str, price_cents: int, quantity: int) -> tuple[Order, list[Trade]]:
        validate_side(side)
        positive_integer(price_cents, "Preço em centavos")
        positive_integer(quantity, "Quantidade")
        order = self._create(side, price_cents, quantity, "limit")
        self._orders[order.id] = order
        return order, self._settle()

    def add_market(self, side: str, quantity: int) -> tuple[Order, list[Trade], int]:
        """Executa a liquidez disponível; retorna também o saldo descartado."""
        validate_side(side)
        positive_integer(quantity, "Quantidade")
        order = self._create(side, None, quantity, "market")
        remaining = quantity
        trades: list[Trade] = []
        while remaining:
            resting = self._best("sell" if side == "buy" else "buy")
            if resting is None:
                break
            executed = min(remaining, resting.quantity)
            buy_id, sell_id = (order.id, resting.id) if side == "buy" else (resting.id, order.id)
            trades.append(Trade(resting.price_cents, executed, buy_id, sell_id))
            self._consume(resting, executed)
            remaining -= executed
            # O consumo da referência pode mudar preços e ativar novos cruzamentos.
            trades.extend(self._settle())
        return order, trades, remaining

    def add_pegged(self, reference: str, side: str, quantity: int) -> tuple[Order, list[Trade]]:
        validate_side(side)
        positive_integer(quantity, "Quantidade")
        if reference not in ("bid", "offer"):
            raise ValueError("Referência deve ser bid ou offer.")
        order = self._create(side, self._references()[reference], quantity, "pegged", reference)
        self._orders[order.id] = order
        return order, self._settle()

    def _find(self, order_id: int) -> Order:
        positive_integer(order_id, "Identificador")
        if order_id not in self._orders:
            raise ValueError(f"Ordem {order_id} não está no livro (inexistente, cancelada ou preenchida).")
        return self._orders[order_id]

    def cancel(self, order_id: int) -> list[Trade]:
        self._find(order_id)
        del self._orders[order_id]
        return self._settle()

    def amend(self, order_id: int, *, price_cents: int | None = None,
              quantity: int | None = None) -> tuple[Order, list[Trade]]:
        """Quantidade informada substitui o saldo, não o total histórico."""
        order = self._find(order_id)
        if price_cents is None and quantity is None:
            raise ValueError("Informe price, qty ou ambos para alterar a ordem.")
        if price_cents is not None:
            positive_integer(price_cents, "Preço em centavos")
            if order.order_type == "pegged":
                raise ValueError("Preço de ordem pegged é automático; altere apenas qty.")
        if quantity is not None:
            positive_integer(quantity, "Quantidade")
        price = order.price_cents if price_cents is None else price_cents
        qty = order.quantity if quantity is None else quantity
        loses_priority = price != order.price_cents or qty > order.quantity
        updated = replace(order, price_cents=price, quantity=qty,
                          arrival_sequence=self._sequence() if loses_priority else order.arrival_sequence)
        self._orders[order_id] = updated
        return updated, self._settle()

    def _references(self) -> dict[str, int | None]:
        # Pegged não define a própria referência nem sustenta outras pegged.
        bids = [o.price_cents for o in self._orders.values()
                if o.order_type == "limit" and o.side == "buy"]
        offers = [o.price_cents for o in self._orders.values()
                  if o.order_type == "limit" and o.side == "sell"]
        return {"bid": max(bids, default=None), "offer": min(offers, default=None)}

    def _refresh_pegs(self) -> None:
        references = self._references()
        for order_id, order in self._orders.items():
            if order.order_type == "pegged":
                self._orders[order_id] = replace(order, price_cents=references[order.peg_reference])

    def _side_orders(self, side: str) -> list[Order]:
        def priority(order: Order) -> tuple[bool, int, int]:
            price = order.price_cents or 0
            return (order.price_cents is None, -price if side == "buy" else price,
                    order.arrival_sequence)
        return sorted((o for o in self._orders.values() if o.side == side), key=priority)

    def buy_orders(self) -> list[Order]:
        return self._side_orders("buy")

    def sell_orders(self) -> list[Order]:
        return self._side_orders("sell")

    def _best(self, side: str) -> Order | None:
        orders = self._side_orders(side)
        return orders[0] if orders and orders[0].price_cents is not None else None

    def _consume(self, order: Order, quantity: int) -> None:
        remaining = order.quantity - quantity
        if remaining:
            self._orders[order.id] = replace(order, quantity=remaining)
        else:
            del self._orders[order.id]

    def _settle(self) -> list[Trade]:
        """Reprecifica e cruza até não haver par compatível.

        Cada trade esgota pelo menos uma ordem; o laço sempre termina.
        """
        trades: list[Trade] = []
        while True:
            self._refresh_pegs()
            buy, sell = self._best("buy"), self._best("sell")
            if buy is None or sell is None or buy.price_cents < sell.price_cents:
                return trades
            resting = min((buy, sell), key=lambda o: o.arrival_sequence)
            quantity = min(buy.quantity, sell.quantity)
            trades.append(Trade(resting.price_cents, quantity, buy.id, sell.id))
            self._consume(buy, quantity)
            self._consume(sell, quantity)

    def render(self) -> str:
        def describe(order: Order) -> str:
            price = format_price(order.price_cents) if order.price_cents is not None else "inativa"
            peg = f" peg {order.peg_reference}" if order.order_type == "pegged" else ""
            return f"{order.quantity} @ {price} id {order.id}{peg}"

        buys = [describe(order) for order in self.buy_orders()]
        sells = [describe(order) for order in self.sell_orders()]
        width = max([len("Ordens de Compra")] + [len(row) for row in buys])
        lines = [f"{'Ordens de Compra':<{width}} | Ordens de Venda", f"{'-' * width}-|-----------------"]
        for buy, sell in zip_longest(buys, sells, fillvalue=""):
            lines.append(f"{buy:<{width}} | {sell}")
        return "\n".join(lines)
