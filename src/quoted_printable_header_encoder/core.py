"""RFC 2047 quoted-printable encoding for email header fields.

The encoder produces ``=?utf-8?Q?...?=`` encoded-words.  Only the ``Q``
encoding is emitted: the ``B`` (base64) encoding is also legal in RFC 2047,
but mixing the two makes the output harder to read and offers no benefit for
the short header fragments this library targets.  That single choice keeps the
code small and the tests honest.

Two public functions are exposed:

``encode_word(text)``
    Encode one already-selected fragment as a single encoded-word.  The
    caller is responsible for ensuring the fragment is short enough that the
    encoded-word does not exceed the 75-character limit from RFC 2047 section
    2.  A ``ValueError`` is raised if the fragment cannot fit.

``encode_header(text, max_line_length=76)``
    Encode an entire header value, splitting it into multiple encoded-words
    separated by CRLF + space (the RFC 5322 folded continuation).  The
    splitting is done on character boundaries; a multi-byte UTF-8 character is
    never split across two encoded-words.
"""

from __future__ import annotations

__all__ = ["encode_header", "encode_word"]

# RFC 2047 section 2 limits an encoded-word to 75 characters total.
_MAX_ENCODED_WORD = 75

# Characters that may appear literally inside a Q-encoded word.  RFC 2047
# section 4.2 says the 8-bit values are encoded, and the printable ASCII set
# minus a few specials may be left alone.  We keep the set conservative so
# that the output is also safe when a MUA re-parses it.
_SAFE = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "!*+-/"
)


def _q_encode_chunk(chunk: str) -> str:
    """Return the body of a Q-encoded word for *chunk*.

    The result does not include the ``=?utf-8?Q?`` prefix or the ``?=``
    suffix.  Spaces are encoded as ``_`` per RFC 2047 section 4.2; every other
    byte outside the safe set becomes ``=XX`` with uppercase hex.
    """
    out: list[str] = []
    for byte in chunk.encode("utf-8"):
        if byte == 0x20:
            out.append("_")
        elif chr(byte) in _SAFE:
            out.append(chr(byte))
        else:
            out.append("=%02X" % byte)
    return "".join(out)


def _encoded_word_length(chunk: str) -> int:
    """Length of the encoded-word that would result from encoding *chunk*."""
    return len("=?utf-8?Q??=") + len(_q_encode_chunk(chunk))


def encode_word(text: str) -> str:
    """Encode *text* as a single RFC 2047 quoted-printable encoded-word.

    The caller chooses the fragment.  If the resulting encoded-word would
    exceed 75 characters (the RFC 2047 limit) a ``ValueError`` is raised
    rather than silently emitting an invalid header.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if text == "":
        raise ValueError("cannot encode an empty string as an encoded-word")
    encoded = _q_encode_chunk(text)
    word = "=?utf-8?Q?" + encoded + "?="
    if len(word) > _MAX_ENCODED_WORD:
        raise ValueError(
            "encoded-word would be %d characters, exceeding the RFC 2047 "
            "limit of %d" % (len(word), _MAX_ENCODED_WORD)
        )
    return word


def _split_into_words(text: str, max_word_length: int = _MAX_ENCODED_WORD) -> list[str]:
    """Split *text* into fragments that each fit in one encoded-word.

    The split happens on character boundaries: a code point is never broken
    across fragments, so a multi-byte UTF-8 sequence is always encoded as a
    unit.  A single character that cannot fit in any encoded-word (which can
    happen only for very long code points combined with a tiny limit) is
    returned on its own so that ``encode_word`` can raise a clear error.
    """
    words: list[str] = []
    current: list[str] = []
    for ch in text:
        candidate = "".join(current) + ch
        if _encoded_word_length(candidate) <= max_word_length:
            current.append(ch)
        else:
            if current:
                words.append("".join(current))
                current = [ch]
            else:
                # The character alone does not fit; emit it so the caller
                # sees a precise error instead of silent data loss.
                words.append(ch)
                current = []
    if current:
        words.append("".join(current))
    return words


def encode_header(text: str, max_line_length: int = 76) -> str:
    """Encode *text* for use as an email header value.

    The value is split into encoded-words that are joined with ``\r\n ``
    (CRLF followed by a single space), which is the folding form required by
    RFC 5322.  *max_line_length* is the maximum length of a folded line
    including the leading space of a continuation; the default of 76 matches
    the common recommendation of leaving room for a header field name.

    A ``ValueError`` is raised if *max_line_length* is too small to hold even
    one encoded-word plus its separator.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a str")
    if not isinstance(max_line_length, int):
        raise TypeError("max_line_length must be an int")
    if text == "":
        return ""
    if max_line_length < len("=?utf-8?Q??=") + 1:
        raise ValueError("max_line_length is too small for any encoded-word")

    # An encoded-word may be at most 75 characters (RFC 2047), and a
    # continuation line starts with a space, so its payload budget is one
    # character smaller than the first line's.  Cap the fragment size to the
    # smaller of the two so every folded line stays within max_line_length.
    max_word_length = min(_MAX_ENCODED_WORD, max_line_length - 1)
    fragments = _split_into_words(text, max_word_length)
    encoded_words = [encode_word(fragment) for fragment in fragments]

    # Greedily pack encoded-words onto lines.
    lines: list[str] = []
    current = ""
    for word in encoded_words:
        if not current:
            current = word
            continue
        candidate = current + " " + word
        if len(candidate) <= max_line_length:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    return "\r\n ".join(lines)
