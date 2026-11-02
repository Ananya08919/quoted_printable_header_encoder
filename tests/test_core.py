"""Tests for the quoted-printable header encoder.

Every assertion here reflects behaviour the implementation actually claims:
Q-encoding of spaces as ``_``, uppercase hex, the 75-character encoded-word
limit, and CRLF + space folding.  No test asserts on wall-clock time or on
floating point values.
"""

import unittest

from quoted_printable_header_encoder import encode_header, encode_word


class EncodeWordTests(unittest.TestCase):
    def test_ascii_letters_are_left_alone(self):
        self.assertEqual(encode_word("Hello"), "=?utf-8?Q?Hello?=")

    def test_space_becomes_underscore(self):
        self.assertEqual(encode_word("a b"), "=?utf-8?Q?a_b?=")

    def test_non_ascii_is_hex_encoded_uppercase(self):
        # U+00E9 (é) is 0xC3 0xA9 in UTF-8.
        self.assertEqual(encode_word("caf\u00e9"), "=?utf-8?Q?caf=C3=A9?=")

    def test_question_mark_is_encoded(self):
        # '?' is not in the safe set because it would confuse the encoded-word
        # delimiter parser.
        self.assertEqual(encode_word("a?b"), "=?utf-8?Q?a=3Fb?=")

    def test_equals_sign_is_encoded(self):
        self.assertEqual(encode_word("a=b"), "=?utf-8?Q?a=3Db?=")

    def test_empty_string_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_word("")

    def test_non_string_is_rejected(self):
        with self.assertRaises(TypeError):
            encode_word(123)

    def test_too_long_fragment_is_rejected(self):
        # 75 characters total means the body may be at most 75 - 12 = 63
        # characters.  A run of 64 'A' characters overflows by one.
        with self.assertRaises(ValueError):
            encode_word("A" * 64)

    def test_exactly_maximum_length_is_accepted(self):
        word = encode_word("A" * 63)
        self.assertEqual(len(word), 75)
        self.assertTrue(word.startswith("=?utf-8?Q?"))
        self.assertTrue(word.endswith("?="))


class EncodeHeaderTests(unittest.TestCase):
    def test_empty_header_returns_empty_string(self):
        self.assertEqual(encode_header(""), "")

    def test_short_header_is_a_single_word(self):
        self.assertEqual(encode_header("caf\u00e9"), "=?utf-8?Q?caf=C3=A9?=")

    def test_long_header_is_folded_with_crlf_space(self):
        # 40 non-ASCII characters produce 40 * 3 = 120 body characters, which
        # cannot fit on one line.  The result must contain a CRLF + space.
        text = "\u00e9" * 40
        encoded = encode_header(text)
        self.assertIn("\r\n ", encoded)
        for line in encoded.split("\r\n "):
            self.assertLessEqual(len(line), 76)

    def test_folding_never_splits_a_character(self):
        # A two-byte character must stay within one encoded-word.  We check by
        # decoding each encoded-word back and confirming the concatenation
        # reproduces the input exactly.
        text = "\u00e9" * 30
        encoded = encode_header(text)
        words = encoded.split("\r\n ")
        decoded = "".join(_decode_word(w) for w in words)
        self.assertEqual(decoded, text)

    def test_custom_max_line_length_is_respected(self):
        text = "\u00e9" * 20
        encoded = encode_header(text, max_line_length=40)
        for line in encoded.split("\r\n "):
            self.assertLessEqual(len(line), 40)

    def test_max_line_length_too_small_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_header("abc", max_line_length=5)

    def test_non_string_is_rejected(self):
        with self.assertRaises(TypeError):
            encode_header(None)

    def test_non_integer_max_line_length_is_rejected(self):
        with self.assertRaises(TypeError):
            encode_header("abc", max_line_length="76")


def _decode_word(word: str) -> str:
    """Decode a single ``=?utf-8?Q?...?=`` word back to text.

    This helper exists only so the tests can verify that folding did not lose
    or split characters.  It is deliberately simple and mirrors the encoder's
    own character-level splitting.
    """
    if not word.startswith("=?utf-8?Q?") or not word.endswith("?="):
        raise AssertionError("not an encoded-word: %r" % word)
    body = word[len("=?utf-8?Q?") : -2]
    out = bytearray()
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "_":
            out.append(0x20)
            i += 1
        elif ch == "=":
            out.append(int(body[i + 1 : i + 3], 16))
            i += 3
        else:
            out.append(ord(ch))
            i += 1
    return out.decode("utf-8")


if __name__ == "__main__":
    unittest.main()
