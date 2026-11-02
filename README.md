# quoted_printable_header_encoder

Encode non-ASCII text into RFC 2047 quoted-printable words for email header fields.

```python
from quoted_printable_header_encoder import encode_header, encode_word

encode_word("caf\u00e9")
# '=?utf-8?Q?caf=C3=A9?='

encode_header("\u00e9" * 40)
# '=?utf-8?Q?=C3=A9=C3=A9...?=\r\n =?utf-8?Q?...?='
```

## Why this exists

Email headers are all-ASCII by specification, so any non-ASCII text in a
``Subject:`` or ``From:`` field has to be wrapped in an RFC 2047 encoded-word.
The two legal encodings are ``Q`` (quoted-printable) and ``B`` (base64); this
library emits only ``Q``.  The trade-off is deliberate: ``Q`` output is
readable in a raw message dump and is shorter for mostly-ASCII text, which is
the common case for display names and subjects.  Purely binary payloads would
be shorter in ``B``, but header values are never binary.

## The awkward edge

An encoded-word is limited to 75 characters, and a multi-byte UTF-8 character
must not be split across two words.  ``encode_header`` therefore splits the
input on character boundaries and folds the result with CRLF + space.  If you
call ``encode_word`` directly with a fragment that is too long, it raises
``ValueError`` instead of emitting an invalid header; use ``encode_header``
when you do not want to reason about the limit yourself.

## API

- ``encode_word(text: str) -> str`` — encode one fragment as a single
  encoded-word.  Raises ``ValueError`` for an empty string or a fragment that
  would exceed 75 characters, and ``TypeError`` for non-``str`` input.
- ``encode_header(text: str, max_line_length: int = 76) -> str`` — encode a
  whole header value, folding with CRLF + space.  Raises ``ValueError`` if
  ``max_line_length`` is too small for any encoded-word, and ``TypeError`` for
  the wrong argument types.
