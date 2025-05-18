import os
import json
import time
import logging
import shutil
import gzip
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import sqlalchemy as sa
from sqlalchemy.ext.serializer import dumps, loads

class BackupManager:
    """
    Backup and recovery manager for the Standup Bot.
    Provides methods for backing up and restoring data.
    """

    def __init__(self, storage_manager, config=None, logger=None):
        """
        Initialize the backup manager.

        Args:
            storage_manager: Storage manager instance.
            config: Optional configuration object.
            logger: Optional logger instance.
        """
        self.storage_manager = storage_manager
        self.config = config
        self.logger = logger or logging.getLogger('standup_bot.backup')

        # Default backup directory
        self.backup_dir = os.environ.get('BACKUP_DIR', './backups')
        if config and hasattr(config, 'backup_dir') and config.backup_dir:
            self.backup_dir = config.backup_dir

        # Create backup directory if it doesn't exist
        os.makedirs(self.backup_dir, exist_ok=True)

        # Backup schedule
        self.backup_interval = int(os.environ.get('BACKUP_INTERVAL_HOURS', '24'))
        self.max_backups = int(os.environ.get('MAX_BACKUPS', '7'))

        # Initialize backup thread
        self.backup_thread = None
        self.running = False

    def start_scheduled_backups(self):
        """Start scheduled backups."""
        if not self.running:
            self.running = True
            self.backup_thread = threading.Thread(target=self._backup_loop, daemon=True)
            self.backup_thread.start()
            self.logger.info(f"Scheduled backups started (interval: {self.backup_interval} hours)")

    def stop_scheduled_backups(self):
        """Stop scheduled backups."""
        self.running = False
        if self.backup_thread:
            self.backup_thread.join(timeout=1.0)
            self.logger.info("Scheduled backups stopped")

    def _backup_loop(self):
        """Background thread that performs scheduled backups."""
        while self.running:
            try:
                # Perform backup
                self.create_backup()

                # Clean up old backups
                self._cleanup_old_backups()

                # Sleep until next backup
                for _ in range(self.backup_interval * 60 * 60):  # Convert hours to seconds
                    if not self.running:
                        break
                    time.sleep(1)
            except Exception as e:
                self.logger.error(f"Error in backup loop: {str(e)}", exc_info=True)
                # Sleep for a while before retrying
                time.sleep(60 * 60)  # 1 hour

    def create_backup(self, backup_name=None) -> str:
        """
        Create a backup of the bot's data.

        Args:
            backup_name: Optional name for the backup. If not provided, a timestamp will be used.

        Returns:
            Path to the created backup file.
        """
        try:
            # Generate backup name if not provided
            if not backup_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"standup_bot_backup_{timestamp}"

            # Create backup file path
            backup_file = os.path.join(self.backup_dir, f"{backup_name}.json.gz")

            # Get data to backup
            backup_data = self._get_backup_data()

            # Write backup to file
            with gzip.open(backup_file, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2)

            self.logger.info(f"Backup created: {backup_file}")
            return backup_file
        except Exception as e:
            self.logger.error(f"Failed to create backup: {str(e)}", exc_info=True)
            raise

    def restore_backup(self, backup_file: str) -> bool:
        """
        Restore data from a backup file.

        Args:
            backup_file: Path to the backup file.

        Returns:
            True if successful, False otherwise.
        """
        try:
            # Check if backup file exists
            if not os.path.exists(backup_file):
                self.logger.error(f"Backup file not found: {backup_file}")
                return False

            # Read backup data
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)

            # Restore data
            self._restore_backup_data(backup_data)

            self.logger.info(f"Backup restored from: {backup_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore backup: {str(e)}", exc_info=True)
            return False

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        List available backups.

        Returns:
            List of dictionaries with backup information.
        """
        backups = []

        try:
            # Get all backup files
            for filename in os.listdir(self.backup_dir):
                if filename.endswith('.json.gz'):
                    file_path = os.path.join(self.backup_dir, filename)
                    file_stat = os.stat(file_path)

                    # Extract timestamp from filename
                    timestamp = None
                    try:
                        # Try to parse timestamp from filename (format: standup_bot_backup_YYYYMMDD_HHMMSS.json.gz)
                        date_part = filename.split('_backup_')[1].split('.')[0]
                        timestamp = datetime.strptime(date_part, '%Y%m%d_%H%M%S')
                    except (IndexError, ValueError):
                        # If parsing fails, use file modification time
                        timestamp = datetime.fromtimestamp(file_stat.st_mtime)

                    backups.append({
                        'filename': filename,
                        'path': file_path,
                        'size': file_stat.st_size,
                        'created': timestamp.isoformat(),
                        'timestamp': timestamp  # For sorting
                    })

            # Sort backups by timestamp (newest first)
            backups.sort(key=lambda x: x['timestamp'], reverse=True)

            # Remove timestamp field (used only for sorting)
            for backup in backups:
                del backup['timestamp']

            return backups
        except Exception as e:
            self.logger.error(f"Failed to list backups: {str(e)}", exc_info=True)
            return []

    def _cleanup_old_backups(self):
        """Remove old backups, keeping only the most recent ones."""
        try:
            backups = self.list_backups()

            # If we have more backups than the maximum, delete the oldest ones
            if len(backups) > self.max_backups:
                for backup in backups[self.max_backups:]:
                    os.remove(backup['path'])
                    self.logger.info(f"Removed old backup: {backup['filename']}")
        except Exception as e:
            self.logger.error(f"Failed to clean up old backups: {str(e)}", exc_info=True)

    def _get_backup_data(self) -> Dict[str, Any]:
        """
        Get data to backup.

        Returns:
            Dictionary with data to backup.
        """
        backup_data = {
            'version': '1.0',
            'timestamp': datetime.now().isoformat(),
            'data': {}
        }

        # If using SQLAlchemy, serialize database objects
        if hasattr(self.storage_manager, 'db_engine') and self.storage_manager.db_engine:
            try:
                # Create a session
                session = self.storage_manager.Session()

                try:
                    # Get all tables
                    metadata = sa.MetaData()
                    metadata.reflect(bind=self.storage_manager.db_engine)

                    # Serialize data from each table
                    for table_name, table in metadata.tables.items():
                        # Query all rows
                        result = session.execute(table.select())
                        rows = [dict(row) for row in result]

                        # Add to backup data
                        backup_data['data'][table_name] = rows
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Failed to backup database: {str(e)}", exc_info=True)

        # Backup Zulip storage data
        try:
            # Use a hardcoded list of known keys instead of trying to get all keys
            known_keys = ['standups', 'user_preferences', 'responses']
            all_data = {}
            for key in known_keys:
                if self.storage_manager.storage.contains(key):
                    all_data[key] = self.storage_manager.storage.get(key)

            backup_data['data']['zulip_storage'] = all_data
        except Exception as e:
            self.logger.error(f"Failed to backup Zulip storage: {str(e)}", exc_info=True)

        return backup_data

    def _restore_backup_data(self, backup_data: Dict[str, Any]) -> None:
        """
        Restore data from backup.

        Args:
            backup_data: Backup data to restore.
        """
        # Check backup version
        version = backup_data.get('version', '1.0')
        if version != '1.0':
            self.logger.warning(f"Backup version mismatch: {version} (expected 1.0)")

        # Restore database data if available
        if hasattr(self.storage_manager, 'db_engine') and self.storage_manager.db_engine:
            try:
                # Create a session
                session = self.storage_manager.Session()

                try:
                    # Get all tables
                    metadata = sa.MetaData()
                    metadata.reflect(bind=self.storage_manager.db_engine)

                    # Begin transaction
                    session.begin()

                    # Clear and restore each table
                    for table_name, table in metadata.tables.items():
                        if table_name in backup_data['data']:
                            # Delete all rows
                            session.execute(table.delete())

                            # Insert rows from backup
                            rows = backup_data['data'][table_name]
                            if rows:
                                # Insert in batches to avoid large transactions
                                batch_size = 100
                                for i in range(0, len(rows), batch_size):
                                    batch = rows[i:i+batch_size]
                                    session.execute(table.insert(), batch)

                    # Commit transaction
                    session.commit()
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            except Exception as e:
                self.logger.error(f"Failed to restore database: {str(e)}", exc_info=True)
                raise

        # Restore Zulip storage data
        try:
            if 'zulip_storage' in backup_data['data']:
                zulip_data = backup_data['data']['zulip_storage']
                for key, value in zulip_data.items():
                    self.storage_manager.storage.put(key, value)
        except Exception as e:
            self.logger.error(f"Failed to restore Zulip storage: {str(e)}", exc_info=True)
            raise
