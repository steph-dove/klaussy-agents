"""The secret scanner must catch real credentials and stay quiet on the rest."""

import pytest

from klaussy.secret_scan import analyze, scan_paths


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        ('aws = "AKIAIOSFODNN7EXAMPLE"', "AWS access key ID"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private key block"),
        ('tok = "ghp_' + "a" * 36 + '"', "GitHub token"),
        ('slack = "xoxb-123456789012-abcdefghijkl"', "Slack token"),
        ('key = "AIza' + "b" * 35 + '"', "Google API key"),
        ('stripe = "sk_live_' + "c" * 24 + '"', "Stripe secret key"),
    ],
)
def test_high_confidence_tokens_flagged(line, kind):
    findings = analyze("f.py", line)
    assert len(findings) == 1
    assert findings[0].kind == kind


def test_generic_high_entropy_credential_flagged():
    findings = analyze("f.py", 'password = "aP9x2Lm7Qz4Rt8Vw1Nb6Kc3"')
    assert len(findings) == 1
    assert findings[0].kind == "hardcoded credential"


@pytest.mark.parametrize(
    "line",
    [
        'api_key = "YOUR_API_KEY_HERE"',  # placeholder
        'token = os.environ["TOKEN"]',  # env lookup, no quoted literal on rhs
        'secret = "${VAULT_SECRET}"',  # template hole
        'password = "changeme"',  # obvious stand-in
        'db_host = "postgres"',  # not a secret name, low entropy
        'note = "aP9x2Lm7Qz4Rt8Vw1Nb6Kc3"',  # high entropy but non-secret name
        'password = "short"',  # too short to be a key
    ],
)
def test_non_secrets_not_flagged(line):
    assert analyze("f.py", line) == []


def test_scope_restricts_to_changed_lines():
    text = 'a = "AKIAIOSFODNN7EXAMPLE"\nb = "AKIAIOSFODNN7EXAMPLE"\n'
    # Only line 2 is "changed" -> line 1's secret is out of scope.
    findings = analyze("f.py", text, scope={2})
    assert len(findings) == 1
    assert findings[0].line == 2


def test_scan_paths_skips_unreadable(tmp_path):
    missing = tmp_path / "nope.py"
    assert scan_paths([str(missing)], diff=False) == []


def test_scan_paths_reports_real_file(tmp_path):
    f = tmp_path / "cfg.py"
    f.write_text('token = "ghp_' + "z" * 36 + '"\n')
    findings = scan_paths([str(f)], diff=False)
    assert len(findings) == 1 and findings[0].kind == "GitHub token"
