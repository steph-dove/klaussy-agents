---
paths:
  - "tests/**/*.py"
---

# Rules for `tests/**/*.py`

## Conventions

- **Test naming: Simple style (test_feature)**: Use Use Simple style (test_feature) naming. 523/539 test functions. Uses 2 test classes for grouping. naming style for all test functions.
  *Example context from `tests/test_utils.py` (lines 22-28):*
  ```python
          "utf-32-le",
      ),
  )
  def test_encoded(encoding):
      content = '{"abc": 123}'.encode(encoding)
      response = httpx.Response(200, content=content)
      assert response.json() == {"abc": 123}
  ```
