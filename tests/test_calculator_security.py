import unittest

from utils.calculator import evaluate_calculator_expression


class CalculatorExpressionSecurityTest(unittest.TestCase):
    def test_supported_math_expression(self):
        self.assertAlmostEqual(
            evaluate_calculator_expression("sqrt(16) + sin(pi / 2) * 3"),
            7.0,
        )

    def test_rejects_python_object_traversal(self):
        with self.assertRaises(ValueError):
            evaluate_calculator_expression(
                "().__class__.__base__.__subclasses__()"
            )

    def test_rejects_import_and_keyword_arguments(self):
        for expression in (
            "__import__('os').system('whoami')",
            "sqrt(x=16)",
        ):
            with self.subTest(expression=expression):
                with self.assertRaises((SyntaxError, ValueError)):
                    evaluate_calculator_expression(expression)

    def test_rejects_resource_abuse_and_non_finite_results(self):
        for expression in ("2 ** 1000000", "1e309"):
            with self.subTest(expression=expression):
                with self.assertRaises(ValueError):
                    evaluate_calculator_expression(expression)


if __name__ == "__main__":
    unittest.main()
