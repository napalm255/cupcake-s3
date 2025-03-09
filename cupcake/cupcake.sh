#!/bin/bash

# Script to perform an AWS S3 sync with locking, logging and statistics.

# Function to display usage and exit
usage() {
  echo "Usage: $0 --source <source> --destination <destination> --log-retention 3 --profile <profile> --storage-class <storage-class> --delete"
  exit 1
}

# Function to check if the script is already running
is_running() {
  if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" > /dev/null; then
      echo ":: Job already running. (PID: $PID)." >> "${LOG_FILE}"
      return 0 # Indicate running
    else
      # Stale lock file, remove it.
      rm "$LOCK_FILE"
      return 1 # Indicate not running
    fi
  else
    return 1 # Indicate not running
  fi
}

# Function to acquire a lock
acquire_lock() {
  echo "$$" > "$LOCK_FILE"
}

# Function to release the lock
release_lock() {
  if [ -f "$LOCK_FILE" ]; then
    rm "$LOCK_FILE"
  fi
}

# Function to update the JSON stats file
update_stats() {
  local stats_file="$1"
  local new_uploaded="$2"
  local new_deleted="$3"
  local new_downloaded="$4"
  local new_last_run="$5"

  # Check if the stats file exists
  if [[ $(stat -c %s "$stats_file" 2> /dev/null) -gt 1 ]]; then
    # Read the existing JSON
    existing_stats=$(cat "$stats_file")
    if [[ -z "$existing_stats" ]]; then
      echo ":: Error: Stats file is empty or invalid JSON."
      return 1
    fi

    # Parse the existing JSON using jq
    existing_uploaded=$(echo "$existing_stats" | jq -r '.uploaded')
    existing_deleted=$(echo "$existing_stats" | jq -r '.deleted')
    existing_downloaded=$(echo "$existing_stats" | jq -r '.downloaded')

    if [[ -z "$existing_uploaded" || -z "$existing_deleted" || -z "$existing_downloaded" ]]; then
        echo ":: Error: Unable to parse existing JSON"
        return 1
    fi

    # Calculate the new values
    new_uploaded=$((existing_uploaded + new_uploaded))
    new_deleted=$((existing_deleted + new_deleted))
    new_downloaded=$((existing_downloaded + new_downloaded))
  else
    # If the file doesn't exist, use the new values directly
    echo ":: Stats file does not exist, creating new file."
  fi

  # Generate the new JSON
  new_json=$(jq -n \
    --argjson uploaded "$new_uploaded" \
    --argjson deleted "$new_deleted" \
    --argjson downloaded "$new_downloaded" \
    --argjson last_run "$new_last_run" \
    '{uploaded: $uploaded | tonumber, deleted: $deleted | tonumber, downloaded: $downloaded | tonumber, last_run: $last_run | tonumber}')

  # Write the new JSON to the stats file
  echo "$new_json" > "$stats_file"
}

# Parse command-line arguments
SOURCE=""
DESTINATION=""
LOG_RETENTION=""
PROFILE=""
STORAGE_CLASS=""
DELETE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE="$2"
      shift 2
      ;;
    --destination)
      DESTINATION="$2"
      shift 2
      ;;
    --log-retention)
      LOG_RETENTION="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --storage-class)
      STORAGE_CLASS="--storage-class $2"
      shift 2
      ;;
    --delete)
      DELETE="--delete"
      shift
      ;;
    *)
      usage
      ;;
  esac
done

# Validate arguments
if [ -z "${PROFILE}" ] || [ -z "${SOURCE}" ] || [ -z "${DESTINATION}" ]; then
  usage
fi

# Configuration
LOG_DIR="/var/log/cupcake"
LOG_FILE="$LOG_DIR/${PROFILE}.log"
LOCK_FILE="$LOG_DIR/${PROFILE}.lock"
STATS_FILE="$LOG_DIR/${PROFILE}.stats"
LOGROTATE_FILE="/etc/logrotate.d/${PROFILE}"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"
mkdir -p "dirname ${LOGROTATE_FILE}"

# Rotate the log file
cat > "${LOGROTATE_FILE}" <<EOF
${LOG_FILE} {
  size 20M
  rotate ${LOG_RETENTION}
  missingok
  notifempty
  create 0644 root root
}
EOF

logrotate "${LOGROTATE_FILE}"

# Grab start time
START_TIME=$(date +%s)
START_TIME_HUMAN=$(date -d @${START_TIME})
echo ":: Started: ${START_TIME_HUMAN}" >> "${LOG_FILE}"

# Check if script is already running
if is_running; then
  exit 1
fi

# Acquire lock
acquire_lock

# Perform s3 sync
echo ":: Sync: Starting" >> "${LOG_FILE}"
SYNC_LOG=$(/usr/bin/aws s3 sync "${SOURCE}" "${DESTINATION}" \
  --no-progress \
  --profile ${PROFILE} \
  ${STORAGE_CLASS} \
  ${DELETE} | tee -a "${LOG_FILE}")
echo ":: Sync: Completed" >> "${LOG_FILE}"

# Parse log file for statistics
UPLOADED_FILES=$(echo "${SYNC_LOG}" | grep -c "upload:")
DELETED_FILES=$(echo "${SYNC_LOG}" | grep -c "delete:")
DOWNLOADED_FILES=$(echo "${SYNC_LOG}" | grep -c "download:")

# Grab end time
END_TIME=$(date +%s)
END_TIME_HUMAN=$(date -d @${END_TIME})

# Calculate duration
DURATION=$((END_TIME - START_TIME))

# Write statistics to file in json format
JSON_STATS="{\"uploaded\": ${UPLOADED_FILES}, \"deleted\": ${DELETED_FILES}, \"downloaded\": ${DOWNLOADED_FILES}, \"duration\": ${DURATION}, \"start_time\": \"${START_TIME_HUMAN}\", \"end_time\": \"${END_TIME_HUMAN}\"}"
echo ":: Stats: ${JSON_STATS}" >> "${LOG_FILE}"

# Update the stats file
update_stats "${STATS_FILE}" "${UPLOADED_FILES}" "${DELETED_FILES}" "${DOWNLOADED_FILES}" "${START_TIME}" >> "${LOG_FILE}"

# Release lock
release_lock

echo ":: Finished: ${END_TIME_HUMAN}" >> "${LOG_FILE}"
echo ":: Duration: ${DURATION} seconds" >> "${LOG_FILE}"
echo ":: -------------------------------------------" >> "${LOG_FILE}"

exit 0
