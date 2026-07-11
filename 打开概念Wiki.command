#!/bin/zsh

ROOT="${0:A:h}"
URL="http://127.0.0.1:4173/"
STATUS_URL="${URL}__wiki_version"
LOG="$ROOT/wiki/server.log"
PYTHON_BIN="$(command -v python3)"

cd "$ROOT" || exit 1

if ! /usr/bin/curl --silent --fail "$STATUS_URL" >/dev/null 2>&1; then
  for pid in $(/usr/sbin/lsof -tiTCP:4173 -sTCP:LISTEN 2>/dev/null); do
    /bin/kill "$pid" 2>/dev/null
  done
  for _ in {1..20}; do
    ! /usr/sbin/lsof -tiTCP:4173 -sTCP:LISTEN >/dev/null 2>&1 && break
    /bin/sleep 0.1
  done

  /usr/bin/nohup "$PYTHON_BIN" "$ROOT/wiki/dev_server.py" >"$LOG" 2>&1 &
  for _ in {1..60}; do
    /usr/bin/curl --silent --fail "$STATUS_URL" >/dev/null 2>&1 && break
    /bin/sleep 0.15
  done
fi

/usr/bin/open "$URL"
