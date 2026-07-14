#!/bin/sh
set -e

chown -R botuser:botuser /app/sessions

exec setpriv --reuid=botuser --regid=botuser --init-groups "$@"
