from io import StringIO
from unittest import TestCase, main
from unittest.mock import patch

from matching_engine.book import OrderBook
from matching_engine.cli import execute, main as cli_main
from matching_engine.order import format_price, parse_price


class PriceTests(TestCase):
    def test_exact_conversion(self):
        for text, cents in [("10", 1000), ("10.50", 1050), ("0.01", 1), (".5", 50),
                            ("123456789012345678901234567890.12", 12345678901234567890123456789012)]:
            with self.subTest(text=text):
                self.assertEqual(parse_price(text), cents)
                self.assertIsInstance(parse_price(text), int)
        self.assertEqual(format_price(1050), "10.50")

    def test_invalid_prices(self):
        for text in ["0", "0.00", "-1", "NaN", "Infinity", "-Infinity", "10.001",
                     "10.000", "1,50", "abc", "", "1e2", "1_000"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_price(text)


class BookTests(TestCase):
    def test_price_time_priority_and_individual_rows(self):
        book = OrderBook()
        for side, price, quantity in [("buy", 1000, 100), ("buy", 1100, 50),
                                      ("buy", 1000, 200), ("sell", 2000, 100),
                                      ("sell", 1900, 80), ("sell", 1900, 30)]:
            book.add_limit(side, price, quantity)
        self.assertEqual([order.id for order in book.buy_orders()], [2, 1, 3])
        self.assertEqual([order.id for order in book.sell_orders()], [5, 6, 4])
        rows = book.render().splitlines()[2:]
        self.assertEqual([row.split("|")[0].strip() for row in rows],
                         ["50 @ 11.00 id 2", "100 @ 10.00 id 1", "200 @ 10.00 id 3"])
        self.assertEqual([row.split("|")[1].strip() for row in rows],
                         ["80 @ 19.00 id 5", "30 @ 19.00 id 6", "100 @ 20.00 id 4"])

    def test_sequential_unique_ids_across_sides(self):
        book = OrderBook()
        orders = [book.add_limit(side, 100, 1)[0] for side in ("buy", "sell", "buy")]
        self.assertEqual([order.id for order in orders], [1, 2, 3])
        self.assertEqual([order.arrival_sequence for order in orders], [1, 2, 3])
        self.assertEqual(OrderBook().buy_orders(), [])

    def test_crossed_orders_execute_at_resting_price(self):
        book = OrderBook()
        book.add_limit("buy", 2000, 10)
        order, trades = book.add_limit("sell", 1000, 10)
        self.assertEqual(order.id, 2)
        self.assertEqual([(t.price_cents, t.quantity, t.buy_order_id, t.sell_order_id)
                          for t in trades], [(2000, 10, 1, 2)])
        self.assertEqual(book.buy_orders(), [])
        self.assertEqual(book.sell_orders(), [])

    def test_empty_and_one_sided_books(self):
        for side in [None, "buy", "sell"]:
            with self.subTest(side=side):
                book = OrderBook()
                if side:
                    book.add_limit(side, 100, 1)
                rendered = book.render()
                self.assertIn("Ordens de Compra", rendered)
                self.assertIn("Ordens de Venda", rendered)
                self.assertEqual(len(rendered.splitlines()), 3 if side else 2)


class CliTests(TestCase):
    def test_invalid_input_preserves_book_and_identifiers(self):
        book = OrderBook()
        execute("limit buy 10 100", book, StringIO())
        before = book.render()
        invalid = ["unknown", "market buy", "limit", "limit buy 10",
                   "limit buy 10 1 extra", "limit other 10 1", "limit buy NaN 1",
                   "limit buy Infinity 1", "limit buy 1.001 1", "limit buy 0 1",
                   "limit sell 10 0", "limit buy 10 -1", "limit buy 10 1.5",
                   "limit buy 10 abc", "print", "print book extra", "help extra", "exit extra"]
        for line in invalid:
            with self.subTest(line=line):
                output = StringIO()
                self.assertTrue(execute(line, book, output))
                self.assertIn("Erro:", output.getvalue())
                self.assertEqual(book.render(), before)
        output = StringIO()
        execute("limit sell 20 1", book, output)
        self.assertEqual(output.getvalue(), "Order created: sell 1 @ 20.00 id 2\n")

    def test_whitespace_help_and_exit(self):
        book, output = OrderBook(), StringIO()
        self.assertTrue(execute("   ", book, output))
        self.assertEqual(output.getvalue(), "")
        execute("  limit   buy  10.50   100  ", book, output)
        self.assertIn("Order created: buy 100 @ 10.50 id 1", output.getvalue())
        execute("print book", book, output)
        self.assertIn("100 @ 10.50 id 1", output.getvalue())
        execute("help", book, output)
        self.assertIn("Comandos:", output.getvalue())
        self.assertFalse(execute(" exit ", book, output))

    def test_eof_exit_and_recovery_in_terminal_loop(self):
        for suffix in ["", "exit\nlimit sell 20 1\n"]:
            with self.subTest(suffix=suffix):
                output = StringIO()
                with patch("sys.stdin", StringIO("bad\nlimit buy 10 100\nprint book\n" + suffix)), patch("sys.stdout", output):
                    cli_main()
                self.assertIn("Erro:", output.getvalue())
                self.assertIn("Order created: buy 100 @ 10.00 id 1", output.getvalue())
                self.assertIn("100 @ 10.00 id 1", output.getvalue())
                self.assertNotIn("Order created: sell", output.getvalue())


if __name__ == "__main__":
    main()
