#!/bin/zsh

ROOT="${0:A:h}"
URL="http://127.0.0.1:4173/"
LOG="$ROOT/wiki/server.log"

cd "$ROOT" || exit 1

if ! /usr/bin/curl --silent --fail "$URL" >/dev/null 2>&1; then
  /usr/bin/nohup /usr/bin/python3 -m http.server 4173 --directory "$ROOT/wiki/dist" >"$LOG" 2>&1 &
  for _ in {1..20}; do
    /usr/bin/curl --silent --fail "$URL" >/dev/null 2>&1 && break
    /bin/sleep 0.15
  done
fi

/usr/bin/open "$URL"
