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
        assert humanize("In my opinion the retry is redundant.") == "The retry is redundant."
        assert humanize("In my honest opinion this is fragile.") == "This is fragile."

    def test_if_you_ask_me(self):
        assert humanize("If you ask me, the cache is stale.") == "The cache is stale."

    def test_opener_only_at_sentence_start_not_midword(self):
        # "personality" must not be clipped by the "Personally" alternative, and a
        # mid-sentence "honestly" is left alone — only line/text-initial openers go.
        assert humanize("The personality module is fine.") == "The personality module is fine."
        assert (
            humanize("This works honestly well in practice.")
            == "This works honestly well in practice."
        )

    def test_opener_inside_code_is_preserved(self):
        # Backticked/fenced content is never scrubbed.
        assert humanize("Run `Personally()` first.") == "Run `Personally()` first."


class TestExtendedScrubber:
    def test_emoji_stripping(self):
        assert humanize("Add user authentication 🚀") == "Add user authentication"
        assert humanize("✨ Refactor database helpers ✨") == "Refactor database helpers"

    def test_transition_openers(self):
        assert humanize("Furthermore, the handler has a bug.") == "The handler has a bug."
        assert humanize("Moreover, we should clean up.") == "We should clean up."

    def test_leverage_utilize_replacement(self):
        assert humanize("We should utilize the new function.") == "We should use the new function."
        assert humanize("This will leverage caches.") == "This will use caches."

    def test_apologies_stripping(self):
        assert humanize("Sorry about that! The handler is correct.") == "The handler is correct."
        assert humanize("Apologies for the confusion. We should use foo.") == "We should use foo."
        assert humanize("My apologies.") == ""

    def test_bot_thanking_stripping(self):
        assert humanize("Thanks @dependabot! We should merge this.") == "We should merge this."
        assert humanize("Thank you for the review, @codecov-bot!") == ""
        assert humanize("Thanks, bot.") == ""


class TestActuallyStripping:
    def test_opener_is_stripped_and_recapitalized(self):
        assert humanize("Actually, this races on startup.") == "This races on startup."
        assert humanize("Actually the lock is wrong.") == "The lock is wrong."

    def test_second_sentence_opener_is_stripped(self):
        assert humanize("It works. Actually it does.") == "It works. It does."
        assert humanize("Fine. Actually, the lock is wrong.") == "Fine. The lock is wrong."

    def test_mid_sentence_adverb_is_dropped(self):
        assert humanize("The retry actually fires twice.") == "The retry fires twice."
        assert humanize("We actually need both branches.") == "We need both branches."

    def test_trailing_adverb_takes_its_comma(self):
        assert humanize("This works, actually.") == "This works."
        assert humanize("The cache is stale actually!") == "The cache is stale!"

    def test_adjective_is_dropped_after_a_determiner(self):
        assert humanize("Read the actual query.") == "Read the query."
        assert humanize("This is their actual root cause.") == "This is their root cause."

    def test_actual_as_a_noun_is_left_alone(self):
        # "the actual" is the noun in test/review prose, not a modifier.
        assert humanize("Compare the actual to the expected.") == (
            "Compare the actual to the expected."
        )
        assert (
            humanize("The actual is 3, the expected is 4.") == "The actual is 3, the expected is 4."
        )
        assert humanize("Check the actual vs expected output.") == (
            "Check the actual vs expected output."
        )

    def test_adjective_left_alone_where_dropping_it_would_break_grammar(self):
        # "an actual bug" would become "an bug" — left to the prompt-side rule.
        assert humanize("That is an actual bug.") == "That is an actual bug."

    def test_no_midword_clipping(self):
        assert humanize("The actuals feed the report.") == "The actuals feed the report."
        assert humanize("Check factual claims.") == "Check factual claims."

    def test_code_is_preserved(self):
        assert humanize("Call `get_actual()` here.") == "Call `get_actual()` here."
