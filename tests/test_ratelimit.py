from ratelimit import RateLimiter


def test_blocks_after_limit_and_reports_wait(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("ratelimit.time.monotonic", lambda: now[0])
    rl = RateLimiter(limit=2, window=60)
    assert rl.check("a") == 0
    assert rl.check("a") == 0
    assert rl.check("a") == 60
    now[0] += 45
    assert rl.check("a") == 15


def test_window_slides_and_clients_are_independent(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("ratelimit.time.monotonic", lambda: now[0])
    rl = RateLimiter(limit=1, window=60)
    assert rl.check("a") == 0
    assert rl.check("b") == 0
    assert rl.check("a") > 0
    now[0] = 60
    assert rl.check("a") == 0


def test_stale_clients_are_pruned(monkeypatch):
    monkeypatch.setattr("ratelimit._MAX_TRACKED_CLIENTS", 3)
    now = [0.0]
    monkeypatch.setattr("ratelimit.time.monotonic", lambda: now[0])
    rl = RateLimiter(limit=1, window=60)
    for k in "abc":
        rl.check(k)
    now[0] = 120
    rl.check("d")
    assert set(rl._hits) == {"d"}
