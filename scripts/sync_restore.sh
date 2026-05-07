#!/bin/bash

# --- CONFIGURATION ---
REMOTE_NAME="r2"
BUCKET_NAME="cue360-prod-backups"
SITE_NAME="dev2.localhost" # Change this to your actual dev site name
RESTORE_DIR="$HOME/latest_restore"
LATEST_MARKER_FILE="$RESTORE_DIR/.latest_folder"

# 1. Ensure restore directory exists
mkdir -p $RESTORE_DIR

echo "Step 1: Finding latest backup folder in R2..."
# Identify the newest folder (e.g., 20260507_000040/)
LATEST_FOLDER=$(rclone lsf $REMOTE_NAME:$BUCKET_NAME | sort -r | head -n 1)

if [ -z "$LATEST_FOLDER" ]; then
    echo "Error: No backup folders found in R2."
    exit 1
fi

LAST_SYNCED_FOLDER=""
if [ -f "$LATEST_MARKER_FILE" ]; then
    LAST_SYNCED_FOLDER=$(cat "$LATEST_MARKER_FILE")
fi

if [ "$LAST_SYNCED_FOLDER" = "$LATEST_FOLDER" ] \
   && find "$RESTORE_DIR" -name "*database.sql.gz" | grep -q . \
   && find "$RESTORE_DIR" -name "*public_files.tar" | grep -q . \
   && find "$RESTORE_DIR" -name "*private_files.tar" | grep -q .; then
    echo "Step 2: Latest backup ($LATEST_FOLDER) already present in $RESTORE_DIR. Skipping download."
else
    echo "Step 2: Downloading $LATEST_FOLDER to $RESTORE_DIR..."
    rm -rf "$RESTORE_DIR"/*
    rclone copy "$REMOTE_NAME:$BUCKET_NAME/$LATEST_FOLDER" "$RESTORE_DIR" --progress
    echo "$LATEST_FOLDER" > "$LATEST_MARKER_FILE"
fi

# Identify the files inside the downloaded folder
DB_FILE=$(find $RESTORE_DIR -name "*database.sql.gz")
PUBLIC_FILES=$(find $RESTORE_DIR -name "*public_files.tar")
PRIVATE_FILES=$(find $RESTORE_DIR -name "*private_files.tar")

echo "Step 3: Restoring to ERPNext site: $SITE_NAME..."
# Run the bench restore
bench --site $SITE_NAME restore "$DB_FILE" \
      --with-public-files "$PUBLIC_FILES" \
      --with-private-files "$PRIVATE_FILES" --force

echo "Step 4: Running Migrations..."
bench --site $SITE_NAME migrate

echo "Done! Dev environment is now synced with Prod backup: $LATEST_FOLDER"
