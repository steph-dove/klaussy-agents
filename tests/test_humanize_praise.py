"""Deterministic coverage for filler/ranking praise leads.

The prompt-side humanize spec tells an agent to cut ranking praise ("Great
catch", "this is the sharpest catch in the review"). The scrubber is the
guaranteed backstop for the fixed short praise phrases, so the stripping must
hold deterministically. Free-form ranking sentences and bot-directed thanks are
context-dependent and stay prompt-side (see the tests at the bottom).
"""

from klaussy.humanize import humanize


class TestPraiseLeads:
    def test_great_catch_comma_is_stripped_and_recapitalized(self):
        assert humanize("Great catch, this races on startup.") == "This races on startup."

    def test_nice_find_period_starts_new_sentence(self):
        assert humanize("Nice find. This leaks the handle.") == "This leaks the handle."

    def test_good_point_lead(self):
        assert humanize("Good point, reverted in 1e9e938.") == "Reverted in 1e9e938."

    def test_excellent_point_and_good_call(self):
        assert humanize("Excellent point: the lock is wrong.") == "The lock is wrong."
        assert humanize("Good call, dropped the field.") == "Dropped the field."

    def test_fixed_phrases(self):
        assert humanize("Well spotted, fixed now.") == "Fixed now."
        assert humanize("Nice one. Pushed the fix.") == "Pushed the fix."

    def test_standalone_praise_line_is_dropped(self):
        assert humanize("Great catch.") == ""
        assert humanize("Great catch!\nThe retry is now bounded.") == "The retry is now bounded."


class TestPraiseLeftAlone:
    def test_praise_word_without_punctuation_is_kept(self):
        # "Good point about X" is a real sentence, not a filler lead — a bare
        # space (no comma/period after the phrase) must not trigger stripping.
        assert (
            humanize("Good point about the retry logic here.")
            == "Good point about the retry logic here."
        )
        assert humanize("Great work on the refactor.") == "Great work on the refactor."

    def test_midsentence_praise_is_kept(self):
        assert (
            humanize("You make a good point, but I disagree.")
            == "You make a good point, but I disagree."
        )

    def test_free_form_ranking_sentence_is_prompt_side_only(self):
        # The scrubber deliberately does NOT strip free-form ranking sentences —
        # generalizing them deterministically would eat legitimate prose. This
        # documents that boundary; the prompt-side guidance handles it.
        text = "This is the sharpest catch in the review."
        assert humanize(text) == text

    def test_praise_inside_code_is_preserved(self):
        assert humanize("Run `Good catch()` first.") == "Run `Good catch()` first."
