# test

Pins matching the repo's existing test framework instead of defaulting to
pytest, and mocking only the external dependency.

## case: matches-existing-unittest-style

The repo already tests with unittest.TestCase; new tests should match, not
switch to pytest.

### instruction
Write tests for the new multiply() function, matching this repo's existing test file's framework and style exactly. Output only the test code.

### context
New function in src/math_ops.py: `def multiply(a, b): return a * b`

Existing tests/test_math_ops.py:
```
import unittest
from src.math_ops import add

class TestMathOps(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
```

### expect
- contains: unittest.testcase | class test
- not contains: import pytest

## case: mocks-only-the-external-call

Only the external HTTP call should be mocked, not the code under test.

### instruction
Write pytest tests for fetch_price. Output only the test code.

### context
```
def fetch_price(symbol):
    resp = requests.get(f"https://api.example.com/price/{symbol}")
    return parse_response(resp.json())

def parse_response(data):
    return data["price"]
```

### expect
- contains: mock | patch
- contains: requests.get
