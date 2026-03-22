"""Simple calculator module for arithmetic operations."""

from typing import Union, List


Number = Union[int, float]


class Calculator:
    """Basic calculator with common operations."""
    
    def add(self, a: Number, b: Number) -> Number:
        """Add two numbers."""
        return a + b
    
    def subtract(self, a: Number, b: Number) -> Number:
        """Subtract b from a."""
        return a - b
    
    def multiply(self, a: Number, b: Number) -> Number:
        """Multiply two numbers."""
        return a * b
    
    def divide(self, a: Number, b: Number) -> Number:
        """Divide a by b.
        
        Raises:
            ValueError: If b is zero.
        """
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    
    def power(self, base: Number, exp: Number) -> Number:
        """Raise base to the power of exp."""
        return base ** exp
    
    def sum_list(self, numbers: List[Number]) -> Number:
        """Sum a list of numbers."""
        return sum(numbers)
    
    def average(self, numbers: List[Number]) -> float:
        """Calculate average of a list of numbers.
        
        Raises:
            ValueError: If list is empty.
        """
        if not numbers:
            raise ValueError("Cannot average empty list")
        return self.sum_list(numbers) / len(numbers)


def scientific_calculator():
    """Factory function for calculator with scientific mode."""
    calc = Calculator()
    calc.scientific_mode = True
    return calc


if __name__ == "__main__":
    # Demo
    calc = Calculator()
    print(f"2 + 3 = {calc.add(2, 3)}")
    print(f"10 / 2 = {calc.divide(10, 2)}")
    print(f"2 ^ 8 = {calc.power(2, 8)}")
