# Data Persistence in Zulip Standup Bot

This document explains how data persistence is implemented in the Zulip Standup Bot to ensure that standup settings and data are preserved across container recreations and deployments.

## Overview

The Zulip Standup Bot uses a combination of automatic backups and restoration to ensure data persistence. When a new version is deployed, the system automatically restores from the latest backup, ensuring that all previous standup settings and data remain intact.

## How It Works

1. **Automatic Backups**: The bot regularly creates backups of all data (standups, responses, reports, user preferences) to a persistent volume.
2. **Persistent Volume**: The `
` directory is configured as a Docker volume, ensuring that backup files are preserved even when the container is recreated.
3. **Automatic Restoration**: When the bot starts, it automatically looks for the latest backup file and restores all data from it.

## Implementation Details

### Backup System

- Backups are stored in the `/app/backups` directory, which is configured as a persistent volume in Docker.
- The backup interval can be configured using the `BACKUP_INTERVAL_HOURS` environment variable (default: 24 hours).
- The maximum number of backups to keep can be configured using the `MAX_BACKUPS` environment variable (default: 7).
- Backups can be disabled by setting the `DISABLE_BACKUPS` environment variable to `true`, `1`, or `yes`.

### Restoration System

- When the bot starts, it automatically looks for the latest backup file in the `/app/backups` directory.
- If a backup is found, it restores all data from it before initializing the bot.
- This ensures that all previous standup settings and data are preserved across deployments.

### Docker Configuration

- The Dockerfile declares `/app/backups` as a volume using the `VOLUME` instruction.
- The captain-definition file is configured to build from the Dockerfile, ensuring that the volume configuration is applied when deploying to CapRover.

## Deployment Considerations

When deploying the Zulip Standup Bot to CapRover or any other Docker-based platform, ensure that:

1. The `/app/backups` volume is properly mounted to a persistent storage location.
2. The `BACKUP_DIR` environment variable is set to `/app/backups` (this is the default).
3. The backup system is not disabled (do not set `DISABLE_BACKUPS` to `true`, `1`, or `yes`).

## Troubleshooting

If data is not persisting across deployments, check the following:

1. Ensure that the `/app/backups` volume is properly mounted to a persistent storage location.
2. Check the logs for any errors related to backup creation or restoration.
3. Verify that backups are being created by looking for `.json.gz` files in the `/app/backups` directory.
4. If using a custom backup directory, ensure that the `BACKUP_DIR` environment variable is set correctly.