# SP Telegram License Service

Separate production licensing backend for the SP Telegram desktop client.

## Security boundary

- PostgreSQL is the intended production database.
- License keys are generated with `secrets` and only their HMAC-SHA256 digest is stored.
- Device identifiers are HMAC-hashed before database storage.
- Ed25519 **private** signing material exists only in this service's environment.
- The desktop application receives only the corresponding public key and signed entitlement.
- Admin API calls require `X-Admin-Token`; ordinary desktop users cannot call administrative plan/status actions.

## Local deployment

Create `.env` from `.env.example`, generate independent random secrets and a 32-byte Ed25519 private key, then run Alembic and seed the exact Starter/Pro/Ultimate plans:

```bash
alembic upgrade head
python -m license_server.app.cli seed-plans
uvicorn license_server.app.main:app --host 127.0.0.1 --port 8001
```

Production must terminate TLS at the service/reverse proxy and expose only HTTPS to the desktop client. Plain HTTP is accepted by the desktop only for loopback development URLs when its explicit development configuration allows it.

## Create a license

```bash
python -m license_server.app.cli create --plan PRO --expires 2026-12-31T23:59:59+00:00
```

The raw key is printed once. Store it securely; the database retains only its digest and non-secret prefix.
