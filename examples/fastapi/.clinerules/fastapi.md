---
paths:
  - "fastapi/**/*.py"
---

# Rules for `fastapi/**/*.py`

## Conventions

- **URL-based API versioning**: Use URL path versioning (e.g., /v1/, /api/v2/).
  *Example context from `fastapi/applications.py` (lines 214-220):*
  ```python
                  ```python
                  from fastapi import FastAPI
  
                  app = FastAPI(openapi_url="/api/v1/openapi.json")
                  ```
                  """
              ),
  ```
- **Data class style: Pydantic for API + dataclasses for internal**: Use Pydantic for API schemas (63) and dataclasses for internal DTOs (10). Good separation.
  *Example context from `fastapi/sse.py` (lines 47-57):*
  ```python
      if v is not None and "\0" in v:
          raise ValueError("SSE 'id' must not contain null characters")
      return _check_single_line(v, "id")
  
  
  class ServerSentEvent(BaseModel):
      """Represents a single Server-Sent Event.
  
      When `yield`ed from a *path operation function* that uses
      `response_class=EventSourceResponse`, each `ServerSentEvent` is encoded
      into the [SSE wire format](https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream)
  ```
- **Background jobs with FastAPI BackgroundTasks**: Use FastAPI BackgroundTasks for background task processing.
  *Example context from `fastapi/background.py` (lines 1-10):*
  ```python
  from collections.abc import Callable
  from typing import Annotated, Any
  
  from annotated_doc import Doc
  from starlette.background import BackgroundTasks as StarletteBackgroundTasks
  from typing_extensions import ParamSpec
  
  P = ParamSpec("P")
  
  ```
- **Data classes: Pydantic models**: Use Pydantic models for structured data. 85/103 structured classes use this pattern.
  *Example context from `fastapi/sse.py` (lines 47-57):*
  ```python
      if v is not None and "\0" in v:
          raise ValueError("SSE 'id' must not contain null characters")
      return _check_single_line(v, "id")
  
  
  class ServerSentEvent(BaseModel):
      """Represents a single Server-Sent Event.
  
      When `yield`ed from a *path operation function* that uses
      `response_class=EventSourceResponse`, each `ServerSentEvent` is encoded
      into the [SSE wire format](https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream)
  ```
- **lowercase constant naming**: Name constants using lowercase style.
  *Example context from `fastapi/params.py` (lines 18-22):*
  ```python
  
  class ParamTypes(Enum):
      query = "query"
      header = "header"
      path = "path"
  ```
- **Enum usage: Enum**: Use Python enums for categorical values. Found 4 enum class(es).
  *Example context from `fastapi/params.py` (lines 14-24):*
  ```python
      Undefined,
  )
  from .datastructures import _Unset
  
  
  class ParamTypes(Enum):
      query = "query"
      header = "header"
      path = "path"
      cookie = "cookie"
  ```
- **Custom decorator pattern: @deprecated**: Use custom decorator @deprecated (4 usages). Also uses: @asynccontextmanager.
  *Example context from `fastapi/responses.py` (lines 34-44):*
  ```python
      orjson = cast(_OrjsonModule, importlib.import_module("orjson"))
  except ModuleNotFoundError:  # pragma: nocover
      orjson = None  # type: ignore[assignment]
  
  
  @deprecated(
      "UJSONResponse is deprecated, FastAPI now serializes data directly to JSON "
      "bytes via Pydantic when a return type or response model is set, which is "
      "faster and doesn't need a custom response class. Read more in the FastAPI "
      "docs: https://fastapi.tiangolo.com/advanced/custom-response/#orjson-or-response-model "
      "and https://fastapi.tiangolo.com/tutorial/response-model/",
  ```
- **Limited exception chaining**: Preserve exception context: use `raise X from Y` or `raise X from None`.
  *Example context from `fastapi/encoders.py` (lines 350-356):*
  ```python
              data = vars(obj)
          except Exception as e:
              errors.append(e)
              raise ValueError(errors) from e
      return jsonable_encoder(
          data,
          include=include,
  ```
- **Mixed validation approaches**: Validate inputs and parameters: Use multiple validation approaches: Pydantic validation, Manual validation (ValueError/TypeError), Decorator-based validation..
  *Example context from `fastapi/encoders.py` (lines 21-27):*
  ```python
  from annotated_doc import Doc
  from fastapi.exceptions import PydanticV1NotSupportedError
  from fastapi.types import IncEx
  from pydantic import BaseModel
  from pydantic.networks import AnyUrl, NameEmail
  from pydantic.types import SecretBytes, SecretStr
  from pydantic_core import PydanticUndefinedType
  ```
