#!/bin/sh
set -e

if [ -n "$WAIT_FOR_HOSTS" ]; then
  echo "Waiting for services..."
  python - "$WAIT_FOR_HOSTS" <<'PY'
import socket, sys, time

targets = sys.argv[1].split()
deadline = time.time() + 90

for target in targets:
    host, port = target.split(":")
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=2):
                break
        except OSError:
            time.sleep(1)
    else:
        print(f"timeout waiting for {target}", file=sys.stderr)
        sys.exit(1)
    print(f"{host}:{port} is ready")
PY
fi

if [ -f alembic.ini ]; then
  echo "Running migrations..."
  alembic upgrade head
fi

exec "$@"