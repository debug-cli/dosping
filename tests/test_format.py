# ═══════════════════════════════════════════════════════════════
#  tests/test_format.py — line format template + field rendering
# ═══════════════════════════════════════════════════════════════

import re

import eventlog


LINE_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\] "
    r"\[(DEBUG|INFO |WARN |ERROR)\] "
    r"\[(app|config|session|flood|scanner|settings|ui|error)\] "
    r"\[([^\]]+)\] "
    r"([a-z0-9_.]+)"
    r"(.*)$"
)


def test_line_template(log_env):
    _, read_log = log_env
    eventlog.log_event(
        "session", "session.attack_started", session="tab-1",
        target="203.0.113.7", ports="80,443", bots=200,
        packet_size=eventlog._fmt_bytes(512), reuse_payload=True,
        source="UI:setup-modal", user_action="LAUNCH",
    )
    body = "\n".join(
        ln for ln in read_log().splitlines() if not ln.startswith("#")
    )
    m = LINE_RE.match(body)
    assert m, body
    ts, level, category, session, event, rest = m.groups()
    assert level == "INFO "
    assert category == "session"
    assert session == "tab-1"
    assert event == "session.attack_started"
    assert 'target=203.0.113.7' in rest
    assert 'bots=200' in rest
    assert 'packet_size=512B' in rest
    assert 'reuse_payload=true' in rest
    assert 'source=UI:setup-modal' in rest  # no space -> unquoted
    assert 'user_action=LAUNCH' in rest


def test_header_line(log_env):
    _, read_log = log_env
    eventlog.log_event("app", "app.start")  # header written on first emit
    text = read_log()
    first = text.splitlines()[0]
    assert first.startswith('# DOSping 3.7.1 "Code Red" log opened')
    assert 'pid=' in first and 'level=normal' in first


def test_sanitization_and_truncation(log_env):
    _, read_log = log_env
    eventlog.log_event(
        "ui", "ui.test", message="line1\nline2\tTabbed", banner="x" * 500
    )
    body = "\n".join(
        ln for ln in read_log().splitlines() if not ln.startswith("#")
    )
    # Newlines/tabs are escaped: the event stays exactly one line.
    assert "line1\\nline2\\tTabbed" in body
    # Long values are truncated with an ellipsis (never a 500-char run).
    assert "x" * 400 not in body
    assert "…" in body


def test_bool_and_number_rendering():
    assert eventlog._sanitize(True) == "true"
    assert eventlog._sanitize(False) == "false"
    assert eventlog._sanitize(200) == "200"
    assert eventlog._sanitize("nospace") == "nospace"
    assert eventlog._sanitize("has spaces") == '"has spaces"'


def test_formatters():
    assert eventlog._fmt_bytes(512) == "512B"
    assert eventlog._fmt_duration(102.4) == "102.4s"
    assert eventlog._fmt_pct(65.12) == "65.1%"
