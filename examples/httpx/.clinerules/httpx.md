---
paths:
  - "httpx/**/*.py"
---

# Rules for `httpx/**/*.py`

## Conventions

- **Data classes: NamedTuple**: Use NamedTuple for structured data. 2/2 structured classes use this pattern.
  *Example context from `httpx/_urlparse.py` (lines 153-163):*
  ```python
  # the stdlib 'ipaddress' module for IP address validation.
  IPv4_STYLE_HOSTNAME = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$")
  IPv6_STYLE_HOSTNAME = re.compile(r"^\[.*\]$")
  
  
  class ParseResult(typing.NamedTuple):
      scheme: str
      userinfo: str
      host: str
      port: int | None
      path: str
  ```
- **lowercase constant naming**: Name constants using lowercase style.
  *Example context from `httpx/_multipart.py` (lines 269-273):*
  ```python
          """
          boundary_length = len(self.boundary)
          length = 0
  
          for field in self.fields:
  ```
- **Enum usage: Enum**: Use Python enums for categorical values. Found 2 enum class(es). Types: Enum (1), IntEnum (1).
  *Example context from `httpx/_client.py` (lines 120-130):*
  ```python
  ACCEPT_ENCODING = ", ".join(
      [key for key in SUPPORTED_DECODERS.keys() if key != "identity"]
  )
  
  
  class ClientState(enum.Enum):
      # UNOPENED:
      #   The client has been instantiated, but has not been used to send a request,
      #   or been opened by entering the context of a `with` block.
      UNOPENED = 1
      # OPENED:
  ```
- **Custom decorator pattern: @click.option**: Use custom decorator @click.option (17 usages).
  *Example context from `httpx/_main.py` (lines 310-320):*
  ```python
      ctx.exit()
  
  
  @click.command(add_help_option=False)
  @click.argument("url", type=str)
  @click.option(
      "--method",
      "-m",
      "method",
      type=str,
      help=(
  ```
- **Limited exception chaining**: Preserve exception context: use `raise X from Y` or `raise X from None`.
  *Example context from `httpx/_decoders.py` (lines 73-79):*
  ```python
              if was_first_attempt:
                  self.decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
                  return self.decode(data)
              raise DecodingError(str(exc)) from exc
  
      def flush(self) -> bytes:
          try:
  ```
- **Context manager usage**: Manage resource lifecycles using context managers (e.g., Use context managers for resource management. 24 with statements. Types: http_client (5).).
  *Example context from `httpx/_main.py` (lines 476-482):*
  ```python
          method = "POST" if content or data or files or json else "GET"
  
      try:
          with Client(proxy=proxy, timeout=timeout, http2=http2, verify=verify) as client:
              with client.stream(
                  method,
                  url,
  ```
- **Configuration via os.environ direct access**: Use os.environ direct access.
  *Example context from `httpx/_config.py` (lines 31-37):*
  ```python
      import certifi
  
      if verify is True:
          if trust_env and os.environ.get("SSL_CERT_FILE"):  # pragma: nocover
              ctx = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
          elif trust_env and os.environ.get("SSL_CERT_DIR"):  # pragma: nocover
              ctx = ssl.create_default_context(capath=os.environ["SSL_CERT_DIR"])
  ```
- **High type annotation coverage**: Standardize on typing: Type annotations are commonly used in this codebase. 396/396 functions have at least one type annotation..
  *Example context from `httpx/_decoders.py` (lines 32-42):*
  ```python
  except ImportError:  # pragma: no cover
      zstandard = None  # type: ignore
  
  
  class ContentDecoder:
      def decode(self, data: bytes) -> bytes:
          raise NotImplementedError()  # pragma: no cover
  
      def flush(self) -> bytes:
          raise NotImplementedError()  # pragma: no cover
  ```
- **Manual validation (ValueError/TypeError)**: Validate inputs and parameters: Use Manual validation (ValueError/TypeError) for input validation. 17/17 validation patterns use this approach..
  *Example context from `httpx/_urls.py` (lines 95-101):*
  ```python
              for key, value in kwargs.items():
                  if key not in allowed:
                      message = f"{key!r} is an invalid keyword argument for URL()"
                      raise TypeError(message)
                  if value is not None and not isinstance(value, allowed[key]):
                      expected = allowed[key].__name__
                      seen = type(value).__name__
  ```
