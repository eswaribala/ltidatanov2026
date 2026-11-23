
#!/usr/bin/env bash
# Splunk Day 3 - Complete Dataset Loader
# Indexes, Web Logs, Application Logs, DB Logs,
# Infrastructure Logs and CSV Lookups

set -euo pipefail

# ----------------------------------------
# 1. Environment validation
# ----------------------------------------

: "${SPLUNK_HOME:?Set SPLUNK_HOME first}"
: "${SPLUNK_AUTH:?Set SPLUNK_AUTH as user:password}"

S="$SPLUNK_HOME/bin/splunk"

if [[ ! -x "$S" ]]; then
    echo "ERROR: Splunk CLI not found at $S"
    exit 1
fi

echo "======================================"
echo " SPLUNK DAY 3 DATASET LOADER"
echo "======================================"

# ----------------------------------------
# 2. Index names
# ----------------------------------------

WEB_INDEX="d3_web_1970"
APP_INDEX="d3_app_1970"
DB_INDEX="d3_db_1970"
INFRA_INDEX="d3_infra_1970"

# ----------------------------------------
# 3. Create indexes if missing
# ----------------------------------------

echo ""
echo "Checking Splunk indexes..."

for idx in \
    "$WEB_INDEX" \
    "$APP_INDEX" \
    "$DB_INDEX" \
    "$INFRA_INDEX"
do
    echo "Checking index: $idx"

    if "$S" list index -auth "$SPLUNK_AUTH" \
        | grep -Fxq "$idx"; then

        echo "Index already exists: $idx"

    else
        echo "Creating index: $idx"
        "$S" add index "$idx" \
            -auth "$SPLUNK_AUTH"
    fi
done

# ----------------------------------------
# 4. Helper function for loading files
# ----------------------------------------

load_file() {
    local filename="$1"
    local index="$2"
    local sourcetype="$3"
    local hostname="$4"

    if [[ ! -f "$filename" ]]; then
        echo "WARNING: File missing: $filename"
        return 0
    fi

    echo "Loading: $filename"
    echo "Index: $index | Host: $hostname"

    "$S" add oneshot "$filename" \
        -index "$index" \
        -sourcetype "$sourcetype" \
        -host "$hostname" \
        -auth "$SPLUNK_AUTH"

    echo "Loaded: $filename"
}

# ----------------------------------------
# 5. Load Web Server Logs
# ----------------------------------------

echo ""
echo "Loading Web Server Logs..."

for h in web-01 web-02
do
    load_file \
        "$PWD/web-$h.log" \
        "$WEB_INDEX" \
        "access_combined" \
        "$h"
done

# ----------------------------------------
# 6. Load Application JSON Logs
# ----------------------------------------

echo ""
echo "Loading Application Logs..."

for h in app-01 app-02 app-03
do
    load_file \
        "$PWD/app-$h.json" \
        "$APP_INDEX" \
        "_json" \
        "$h"
done

# ----------------------------------------
# 7. Load PostgreSQL Database Logs
# ----------------------------------------

echo ""
echo "Loading PostgreSQL Logs..."

load_file \
    "$PWD/db-db-01.log" \
    "$DB_INDEX" \
    "postgresql_lab" \
    "db-01"

# ----------------------------------------
# 8. Load Infrastructure Syslogs
# ----------------------------------------

echo ""
echo "Loading Infrastructure Syslogs..."

for h in app-01 app-02 app-03 db-01
do
    load_file \
        "$PWD/syslog-$h.log" \
        "$INFRA_INDEX" \
        "syslog" \
        "$h"
done

# ----------------------------------------
# 9. Copy CSV Lookup Files
# ----------------------------------------

echo ""
echo "Installing CSV Lookups..."

LOOKUP_DIR="$SPLUNK_HOME/etc/apps/search/lookups"

LOOKUP_FILES=(
    "host_inventory.csv"
    "service_owners.csv"
    "itsi_kpis.csv"
    "itsi_health.csv"
)

if [[ -d "$LOOKUP_DIR" ]]; then
    for file in "${LOOKUP_FILES[@]}"
    do
        if [[ -f "$file" ]]; then
            if cp "$file" "$LOOKUP_DIR/"; then
                echo "Installed lookup: $file"
            else
                echo "WARNING: Cannot copy $file"
                echo "Check write permissions on $LOOKUP_DIR"
            fi
        else
            echo "WARNING: Lookup missing: $file"
        fi
    done
else
    echo "WARNING: Lookup directory not found."
    echo "Expected: $LOOKUP_DIR"
fi

# ----------------------------------------
# 10. Completion
# ----------------------------------------

echo ""
echo "======================================"
echo " SPLUNK DAY 3 LOADING COMPLETED"
echo "======================================"

echo ""
echo "Indexes:"
echo "  $WEB_INDEX"
echo "  $APP_INDEX"
echo "  $DB_INDEX"
echo "  $INFRA_INDEX"

echo ""
echo "Wait about 30 seconds for indexing."

echo ""
echo "Run this Splunk Search:"
echo ""
echo 'index=d3_*_1970 earliest=0'
echo '| stats count by index, sourcetype, host'
echo ""
