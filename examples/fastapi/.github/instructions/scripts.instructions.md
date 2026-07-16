---
applyTo: "scripts/**/*.py"
---

## Conventions

- **Context manager usage**: Manage resource lifecycles using context managers (e.g., Use context managers for resource management. 37 with statements (23 sync, 14 async). Types: file_io (4), threading (2).).
  *Example context from `scripts/docs.py` (lines 853-859):*
  ```python
      in_code_block4 = False
      permalinks = set()
  
      with path.open("r", encoding="utf-8") as f:
          lines = f.readlines()
  
      for line in lines:
  ```
- **Structured configuration with Pydantic Settings**: Use Pydantic BaseSettings for configuration management.
  *Example context from `scripts/label_approved.py` (lines 12-18):*
  ```python
      number: int
  
  
  default_config = {"approved-2": LabelSettings(await_label="awaiting-review", number=2)}
  
  
  class Settings(BaseSettings):
  ```
