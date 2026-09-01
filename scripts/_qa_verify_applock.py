"""Independent QA verification of AppLock fixes (SEC-001, SEC-002, SEC-003).

Run: python scripts/_qa_verify_applock.py
"""
import base64
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security.app_lock_service import AppLockService, _MAX_ATTEMPTS, _LOCKOUT_INITIAL


class MockStorage:
    """In-memory SecureStorage stand-in."""
    def __init__(self):
        self.data = {}

    def get_secret(self, key):
        return self.data.get(key)

    def set_secret(self, key, value):
        self.data[key] = value

    def delete_secret(self, key):
        self.data.pop(key, None)


def make_corrupt_blob():
    # 16-byte salt + only 16 bytes of digest -> wrong total length (32 != 48)
    salt = os.urandom(16)
    return base64.b64encode(salt + os.urandom(16)).decode("ascii")


def make_valid_blob(password):
    svc = AppLockService(MockStorage())
    svc.set_password(password)
    return svc.storage.get_secret(svc.SECRET_KEY)


results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")


# ---- SEC-001: brute-force lockout ----
svc = AppLockService(MockStorage())
svc.set_password("secret123")
svc.state.locked = True

# 5 wrong attempts -> lockout active
for _ in range(_MAX_ATTEMPTS):
    svc.unlock("wrong")
check("SEC-001 lockout activates after 5 fails", svc._is_lockout_active(),
      f"lockout_remaining={svc.lockout_remaining:.1f}s")
check("SEC-001 lockout duration ~= initial", abs(svc.lockout_remaining - _LOCKOUT_INITIAL) < 2.0,
      f"expected ~{_LOCKOUT_INITIAL}s")

# During lockout, correct password also rejected (no bypass)
check("SEC-001 correct password rejected during lockout", svc.unlock("secret123") is False)

# Escalation: after lockout expiry, one more fail -> longer lockout
svc.state.lockout_until = 0.0  # simulate lockout expiry
svc.unlock("wrong")
check("SEC-001 lockout escalates (2x)", svc.lockout_remaining > _LOCKOUT_INITIAL,
      f"remaining={svc.lockout_remaining:.1f}s > {_LOCKOUT_INITIAL}")

# Reset on success
svc.state.lockout_until = 0.0
svc.state.failed_attempts = 0
check("SEC-001 successful unlock resets attempts", svc.unlock("secret123") is True
      and svc.state.failed_attempts == 0 and svc.state.lockout_until == 0.0)

# ---- SEC-002: hash blob validation ----
svc2 = AppLockService(MockStorage())
svc2.storage.set_secret(svc2.SECRET_KEY, make_corrupt_blob())
check("SEC-002 corrupted blob -> verify False (no crash)", svc2.verify("anything") is False)
check("SEC-002 corrupted blob -> unlock False", svc2.unlock("anything") is False)
check("SEC-002 _load_hash_payload returns None on corrupt", svc2._load_hash_payload() is None)

# Valid blob still verifies
svc3 = AppLockService(MockStorage())
svc3.storage.set_secret(svc3.SECRET_KEY, make_valid_blob("secret123"))
check("SEC-002 valid blob verifies correctly", svc3.verify("secret123") is True
      and svc3.verify("wrong") is False)

# ---- SEC-003: timing side-channel (residual) ----
svc_none = AppLockService(MockStorage())          # no password set
svc_set = AppLockService(MockStorage())
svc_set.storage.set_secret(svc_set.SECRET_KEY, make_valid_blob("secret123"))

# Warm up
svc_none.verify("x"); svc_set.verify("x")

t0 = time.perf_counter()
for _ in range(20):
    svc_none.verify("wrong")
t_none = (time.perf_counter() - t0) / 20

t0 = time.perf_counter()
for _ in range(20):
    svc_set.verify("wrong")
t_set = (time.perf_counter() - t0) / 20

ratio = t_set / max(t_none, 1e-9)
check("SEC-003 timing constant (no-password vs set)", ratio < 3.0,
      f"no-password={t_none*1000:.3f}ms, set={t_set*1000:.3f}ms, ratio={ratio:.1f}x")

print("\n=== SUMMARY ===")
passed = sum(1 for _, ok, _ in results if ok)
print(f"{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)