#!/usr/bin/env bash
# Local host recovery only. Never remove volumes, containers or content.
set -u
umask 077
cd /srv/spin-clinic || exit 1
state=/var/lib/spin-watchdog
mkdir -p "$state" || exit 1
# systemd serializes oneshot starts; also guard direct invocations.
if ! mkdir "$state/running" 2>/dev/null; then
    logger -t spin-watchdog 'Previous watchdog invocation is still active.'
    exit 0
fi
trap 'rmdir "$state/running" 2>/dev/null || true' EXIT
compose=(docker compose --env-file /srv/spin-clinic/.env.production -f /srv/spin-clinic/deploy/docker-compose.production.yml)
log() { logger -t spin-watchdog -- "$*"; }
save() { printf '%s\n' "$2" > "$state/$1.tmp" && mv "$state/$1.tmp" "$state/$1"; }
read_number() {
    local value=0
    [[ ! -f "$state/$1" ]] || read -r value < "$state/$1"
    [[ "$value" =~ ^[0-9]{1,12}$ ]] || value=0
    printf '%s' "$((10#$value))"
}
for service in frontend backend worker beat caddy db redis; do
    # ps failure is not evidence that all services are down (e.g. Docker daemon).
    if ! ids=$("${compose[@]}" ps -q --all "$service" 2>/dev/null); then
        log "Cannot inspect service: $service"
        continue
    fi
    running=false
    if [[ -n "$ids" ]]; then
        running=true
        for id in $ids; do
            [[ "$(docker inspect --format '{{.State.Running}}' "$id" 2>/dev/null)" == true ]] || running=false
        done
    fi
    if [[ "$running" != true ]]; then
        if "${compose[@]}" up -d "$service" >/dev/null 2>&1; then
            log "Started service: $service"
        else
            log "Failed to start service: $service"
        fi
    fi
done

# Override URL via the unit's Environment= for a deployment with another domain.
base_url=${SPIN_WATCHDOG_URL:-https://spin.clinic}
restart_needed=false
for endpoint in home health; do
    path=/
    [[ "$endpoint" != health ]] || path=/api/health/
    failures=$(read_number "$endpoint-failures")
    if curl --fail --silent --output /dev/null --connect-timeout 10 --max-time 25 "$base_url$path"; then
        failures=0
    else
        failures=$((failures + 1))
        log "HTTP check failed: $endpoint ($failures)"
    fi
    save "$endpoint-failures" "$failures" || exit 1
    (( failures < 3 )) || restart_needed=true
done
now=$(date +%s)
last_restart=$(read_number last-restart)
if [[ "$restart_needed" == true ]] && (( now - last_restart >= 1800 )); then
    # Reserve cooldown before Docker; even an ambiguous failure must not loop.
    save last-restart "$now" || exit 1
    if "${compose[@]}" restart frontend backend >/dev/null 2>&1; then
        log 'Restarted frontend and backend after three consecutive HTTP failures.'
        save home-failures 0
        save health-failures 0
    else
        log 'Failed to restart frontend and backend; cooldown retained.'
    fi
fi

# POSIX df output: percent used is column 5. Only the filesystem of the repo.
disk_used=$(df -P /srv/spin-clinic 2>/dev/null | awk 'NR == 2 {gsub(/%/, "", $5); print $5}')
if [[ "$disk_used" =~ ^[0-9]+$ ]] && (( disk_used > 90 )); then
    log 'Disk free below 10%; pruning dangling images and build cache older than 7 days.'
    docker image prune -f >/dev/null 2>&1 || log 'Image prune failed.'
    docker builder prune -f --filter until=168h >/dev/null 2>&1 || log 'Builder prune failed.'
fi
