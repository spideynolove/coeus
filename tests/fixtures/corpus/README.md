# Corpus Fixtures

This directory contains fixture corpora for testing the retrieval pipeline.

## Structure

- `auth_repo/`: Authentication-related code
  - `auth.py`: AuthService class with password hashing and user management
  
- `code_repo/`: General utility code
  - `calculator.py`: Calculator class with arithmetic operations
  - `utils.py`: Utility functions and decorators

## Usage

These fixtures are used as baseline input for:
- Retrieval tests
- Evaluation benchmarks
- Regression detection

## Stability

Do not modify these files without updating the expected retrieval results.
They serve as the stable reference point for V1.
