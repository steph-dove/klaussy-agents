---
paths:
  - "tests/**/*.py"
---

# Rules for `tests/**/*.py`

## Conventions

- **FastAPI-style session dependency injection**: Use get_db() dependency pattern with Depends() for session lifecycle.
  *Example context from `tests/test_security_scopes.py` (lines 10-20):*
  ```python
      return {"count": 0}
  
  
  @pytest.fixture(name="app")
  def app_fixture(call_counter: dict[str, int]):
      def get_db():
          call_counter["count"] += 1
          return f"db_{call_counter['count']}"
  
      def get_user(db: Annotated[str, Depends(get_db)]):
          return "user"
  ```
- **HTTP errors raised in service layer**: HTTPException is frequently raised outside the API layer.
  *Example context from `tests/test_starlette_exception.py` (lines 9-19):*
  ```python
  
  
  @app.get("/items/{item_id}")
  async def read_item(item_id: str):
      if item_id not in items:
          raise HTTPException(
              status_code=404,
              detail="Item not found",
              headers={"X-Error": "Some custom header"},
          )
      return {"item": items[item_id]}
  ```
- **Semi-centralized exception handling**: Exception handlers are spread across 2 modules.
  *Example context from `tests/test_validation_error_context.py` (lines 27-37):*
  ```python
  captured_exception = ExceptionCapture()
  
  app.mount(path="/sub", app=sub_app)
  
  
  @app.exception_handler(RequestValidationError)
  @sub_app.exception_handler(RequestValidationError)
  async def request_validation_handler(request: Request, exc: RequestValidationError):
      captured_exception.capture(exc)
      raise exc
  ```
- **OAuth2 authentication**: Use OAuth2 for authentication. OAuth2 usages: 13.
  *Example context from `tests/test_dependency_paramless.py` (lines 1-9):*
  ```python
  from typing import Annotated
  
  from fastapi import FastAPI, HTTPException, Security
  from fastapi.security import (
      OAuth2PasswordBearer,
      SecurityScopes,
  )
  from fastapi.testclient import TestClient
  ```
- **Mocking with pytest monkeypatch fixture**: Use pytest monkeypatch fixture for test mocking. Also uses: unittest.mock / Mock, @patch decorator.
  *Example context from `tests/test_frontend.py` (lines 24-34):*
  ```python
          calls.append(name)
  
      return dependency
  
  
  def test_frontend_exact_prefix_path_serves_index(tmp_path: Path):
      dist = tmp_path / "dist"
      write_file(dist / "index.html", "app")
      app = FastAPI()
      app.frontend("/", directory=dist)
  ```
- **Test naming: Simple style (test_feature)**: Use Use Simple style (test_feature) naming. 2213/2272 test functions. naming style for all test functions.
  *Example context from `tests/test_datastructures.py` (lines 8-14):*
  ```python
  from fastapi.testclient import TestClient
  
  
  def test_upload_file_invalid_pydantic_v2():
      with pytest.raises(ValueError):
          UploadFile._validate("not a Starlette UploadFile", {})
  ```
