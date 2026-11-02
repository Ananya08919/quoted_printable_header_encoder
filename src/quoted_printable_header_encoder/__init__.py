"""Public API for quoted_printable_header_encoder.

Only the names re-exported here are part of the stable surface; the
implementation lives in :mod:`quoted_printable_header_encoder.core` so that the
package can grow without changing import paths.
"""

from .core import encode_header, encode_word

__all__ = ["encode_header", "encode_word"]
