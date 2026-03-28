from src.core.security import hash_token


def test_hash_token_is_stable():
    t = "abc"
    pepper = "pepper"
    assert hash_token(t, pepper=pepper) == hash_token(t, pepper=pepper)


def test_hash_token_changes_with_pepper():
    t = "abc"
    assert hash_token(t, pepper="p1") != hash_token(t, pepper="p2")
