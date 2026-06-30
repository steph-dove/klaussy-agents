---
paths:
  - "scripts/**/*.py"
---

# Rules for `scripts/**/*.py`

## Conventions

- **Context manager usage**: Manage resource lifecycles using context managers (e.g., Use context managers for resource management. 33 with statements (22 sync, 11 async). Types: file_io (4).).
  *Example context from `scripts/docs.py` (lines 853-859):*
  ```python
      in_code_block4 = False
      permalinks = set()
  
      with path.open("r", encoding="utf-8") as f:
          lines = f.readlines()
  
      for line in lines:
  ```
- **Structured configuration with Pydantic Settings**: Use Pydantic BaseSettings for configuration management.
  *Example context from `scripts/contributors.py` (lines 237-243):*
  ```python
  
  def main() -> None:
      logging.basicConfig(level=logging.INFO)
      settings = Settings()  # ty: ignore[missing-argument]
      logging.info(f"Using config: {settings.model_dump_json()}")
      g = Github(settings.github_token.get_secret_value())
      repo = g.get_repo(settings.github_repository)
  ```
