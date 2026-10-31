import unittest
from app import VERSION, greet


class GreetingTests(unittest.TestCase):
    def test_default(self):
        self.assertEqual(greet(), "Hello, reader!")

    def test_named_reader(self):
        self.assertEqual(greet("Ada"), "Hello, Ada!")

    def test_unicode(self):
        self.assertEqual(greet("Анна"), "Hello, Анна!")

    def test_trims_outer_spaces(self):
        self.assertEqual(greet(" Ada "), "Hello, Ada!")

    def test_empty_is_rejected(self):
        with self.assertRaises(ValueError):
            greet(" ")

    def test_version(self):
        self.assertEqual(VERSION, "1.0")


if __name__ == "__main__":
    unittest.main()
