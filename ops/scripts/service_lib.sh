#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STATE_DIR="$ROOT_DIR/.stacksmith/run"
LOG_DIR="$ROOT_DIR/.stacksmith/logs"

BACKEND_NAME="stacksmith-web"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8765"
BACKEND_PIDFILE="$STATE_DIR/backend.pid"
BACKEND_LOGFILE="$LOG_DIR/backend.log"

FRONTEND_NAME="stacksmith-frontend"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="5173"
FRONTEND_PIDFILE="$STATE_DIR/frontend.pid"
FRONTEND_LOGFILE="$LOG_DIR/frontend.log"

ensure_dirs() {
  mkdir -p "$STATE_DIR" "$LOG_DIR"
}

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pidfile() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] || return 1
  tr -d '[:space:]' < "$pidfile"
}

port_in_use() {
  local host="$1"
  local port="$2"
  python3 - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.25)
try:
    s.connect((host, port))
except OSError:
    sys.exit(1)
sys.exit(0)
PY
}

managed_service_running() {
  local pidfile="$1"
  local pid=""
  if pid="$(read_pidfile "$pidfile" 2>/dev/null)" && is_pid_running "$pid"; then
    return 0
  fi
  rm -f "$pidfile"
  return 1
}

port_pids() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | awk 'NF' | sort -u
    return 0
  fi

  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$port" 2>/dev/null | tr ' ' '\n' | awk 'NF' | sort -u
    return 0
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null \
      | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' \
      | sort -u
    return 0
  fi
}

force_kill_port_users() {
  local host="$1"
  local port="$2"
  local service_name="$3"

  if ! port_in_use "$host" "$port"; then
    return 0
  fi

  mapfile -t pids < <(port_pids "$port")
  if [[ "${#pids[@]}" -eq 0 ]]; then
    echo "[warn] $service_name port $port is in use but no PID lookup tool found"
    return 1
  fi

  echo "[force] $service_name port $port in use; killing occupant PID(s): ${pids[*]}"
  local pid
  for pid in "${pids[@]}"; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    if is_pid_running "$pid"; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  done

  if wait_for_port "$host" "$port" 20 0.1; then
    echo "[warn] $service_name port $port still appears busy after kill attempts"
    return 1
  fi
  return 0
}

is_service_running() {
  local pidfile="$1"
  local host="$2"
  local port="$3"

  local pid=""
  if pid="$(read_pidfile "$pidfile" 2>/dev/null)"; then
    if is_pid_running "$pid"; then
      return 0
    fi
    rm -f "$pidfile"
  fi

  if port_in_use "$host" "$port"; then
    return 0
  fi
  return 1
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local attempts="${3:-30}"
  local delay_sec="${4:-0.25}"

  local i
  for ((i = 0; i < attempts; i++)); do
    if port_in_use "$host" "$port"; then
      return 0
    fi
    sleep "$delay_sec"
  done
  return 1
}

start_backend() {
  if managed_service_running "$BACKEND_PIDFILE"; then
    echo "[skip] $BACKEND_NAME already running on ${BACKEND_HOST}:${BACKEND_PORT}"
    return 0
  fi
  if port_in_use "$BACKEND_HOST" "$BACKEND_PORT"; then
    force_kill_port_users "$BACKEND_HOST" "$BACKEND_PORT" "$BACKEND_NAME"
  fi

  echo "[start] $BACKEND_NAME"
  (
    cd "$ROOT_DIR"
    STACKSMITH_WEB_DEV="${STACKSMITH_WEB_DEV:-true}" \
    STACKSMITH_WEB_HOST="$BACKEND_HOST" STACKSMITH_WEB_PORT="$BACKEND_PORT" \
      nohup stacksmith-web >"$BACKEND_LOGFILE" 2>&1 &
    echo $! >"$BACKEND_PIDFILE"
  )

  if wait_for_port "$BACKEND_HOST" "$BACKEND_PORT"; then
    echo "[ok] $BACKEND_NAME started (log: $BACKEND_LOGFILE)"
  else
    echo "[warn] $BACKEND_NAME process started but port check failed"
    echo "       inspect log: $BACKEND_LOGFILE"
    return 1
  fi
}

start_frontend() {
  if managed_service_running "$FRONTEND_PIDFILE"; then
    echo "[skip] $FRONTEND_NAME already running on ${FRONTEND_HOST}:${FRONTEND_PORT}"
    return 0
  fi
  if port_in_use "$FRONTEND_HOST" "$FRONTEND_PORT"; then
    force_kill_port_users "$FRONTEND_HOST" "$FRONTEND_PORT" "$FRONTEND_NAME"
  fi

  echo "[start] $FRONTEND_NAME"
  local npm_cmd=""
  if command -v npm >/dev/null 2>&1; then
    npm_cmd="$(command -v npm)"
  elif [[ -s "$HOME/.nvm/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    source "$HOME/.nvm/nvm.sh"
    if command -v npm >/dev/null 2>&1; then
      npm_cmd="$(command -v npm)"
    fi
  fi
  if [[ -z "$npm_cmd" ]]; then
    echo "[error] npm not found. Install Node/npm or load your shell runtime manager first."
    return 1
  fi

  (
    cd "$ROOT_DIR/apps/web"
    nohup "$npm_cmd" run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT" \
      >"$FRONTEND_LOGFILE" 2>&1 &
    echo $! >"$FRONTEND_PIDFILE"
  )

  if wait_for_port "$FRONTEND_HOST" "$FRONTEND_PORT"; then
    echo "[ok] $FRONTEND_NAME started (log: $FRONTEND_LOGFILE)"
  else
    echo "[warn] $FRONTEND_NAME process started but port check failed"
    echo "       inspect log: $FRONTEND_LOGFILE"
    return 1
  fi
}

stop_service() {
  local service_name="$1"
  local pidfile="$2"
  local host="$3"
  local port="$4"

  if ! managed_service_running "$pidfile" && ! port_in_use "$host" "$port"; then
    echo "[skip] $service_name already stopped"
    rm -f "$pidfile"
    return 0
  fi

  local pid=""
  if managed_service_running "$pidfile" && pid="$(read_pidfile "$pidfile" 2>/dev/null)"; then
    echo "[stop] $service_name (pid=$pid)"
    kill "$pid" 2>/dev/null || true

    local i
    for ((i = 0; i < 20; i++)); do
      if ! is_pid_running "$pid"; then
        break
      fi
      sleep 0.2
    done

    if is_pid_running "$pid"; then
      echo "[stop] $service_name still running; sending SIGKILL"
      kill -9 "$pid" 2>/dev/null || true
    fi
  else
    echo "[stop] $service_name has no live pidfile process; forcing port cleanup"
    force_kill_port_users "$host" "$port" "$service_name" || true
  fi

  rm -f "$pidfile"
  echo "[ok] $service_name stopped"
}
