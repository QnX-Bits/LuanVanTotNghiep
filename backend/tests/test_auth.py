from app.auth import make_session, resolve_session


def test_signed_session_validates_and_expires():
    token = make_session("an", now=1_000)
    assert resolve_session(token, now=1_001)["role"] == "investor"
    assert resolve_session(token, now=1 + 8 * 60 * 60 + 1000) is None


def test_signed_session_rejects_tampering():
    token = make_session("an", now=1_000)
    changed = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert resolve_session(changed, now=1_001) is None
