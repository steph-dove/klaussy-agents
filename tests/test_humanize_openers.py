"""Deterministic coverage for the verdict/editorializing openers.

These are the openers added so the scrubber strips dismissive lead-ins
("Personally I don't find this useful", "Honestly, ...") regardless of how
well a model complied with the prompt-side humanization spec. The scrubber is
the guaranteed backstop, so the stripping must hold deterministically.
"""

from klaussy.humanize import humanize


class TestVerdictOpeners:
    def test_personally_is_stripped_and_recapitalized(self):
        assert (
            humanize("Personally I don't find these tests useful.")
            == "I don't find these tests useful."
        )

    def test_honestly_with_comma(self):
        assert humanize("Honestly, this races on startup.") == "This races on startup."

    def test_frankly_variants(self):
        assert humanize("Frankly this is slow.") == "This is slow."
        assert humanize("Quite frankly, the lock is wrong.") == "The lock is wrong."

    def test_opinion_openers(self):
        assert humanize("IMO we should rethrow here.") == "We should rethrow here."
        assert humanize("IMHO this leaks.") == "This leaks."
        assert (
            humanize("In my opinion the retry is redundant.")
            == "The retry is redundant."
        )
        assert (
            humanize("In my honest opinion this is fragile.") == "This is fragile."
        )

    def test_if_you_ask_me(self):
        assert humanize("If you ask me, the cache is stale.") == "The cache is stale."

    def test_opener_only_at_sentence_start_not_midword(self):
        # "personality" must not be clipped by the "Personally" alternative, and a
        # mid-sentence "honestly" is left alone — only line/text-initial openers go.
        assert (
            humanize("The personality module is fine.")
            == "The personality module is fine."
        )
        assert (
            humanize("This works honestly well in practice.")
            == "This works honestly well in practice."
        )

    def test_opener_inside_code_is_preserved(self):
        # Backticked/fenced content is never scrubbed.
        assert humanize("Run `Personally()` first.") == "Run `Personally()` first."
