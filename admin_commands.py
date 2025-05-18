import logging
import time
import os
import json
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta

class AdminCommands:
    """
    Admin commands for maintenance of the Standup Bot.
    Provides methods for performing administrative tasks.
    """

    def __init__(self,
                 bot_handler,
                 storage_manager,
                 error_handler=None,
                 monitoring=None,
                 backup_manager=None,
                 rate_limiter=None,
                 health_check_server=None,
                 logger=None):
        """
        Initialize the admin commands.

        Args:
            bot_handler: Zulip bot handler.
            storage_manager: Storage manager instance.
            error_handler: Optional error handler instance.
            monitoring: Optional monitoring instance.
            backup_manager: Optional backup manager instance.
            rate_limiter: Optional rate limiter instance.
            health_check_server: Optional health check server instance.
            logger: Optional logger instance.
        """
        self.bot_handler = bot_handler
        self.storage_manager = storage_manager
        self.error_handler = error_handler
        self.monitoring = monitoring
        self.backup_manager = backup_manager
        self.rate_limiter = rate_limiter
        self.health_check_server = health_check_server
        self.logger = logger or logging.getLogger('standup_bot.admin')

        # List of admin user IDs
        self.admin_ids = set()

        # Load admin IDs from environment variable if available
        admin_ids_str = os.environ.get('STANDUP_BOT_ADMIN_IDS', '')
        if admin_ids_str:
            try:
                self.admin_ids = set(int(id_str) for id_str in admin_ids_str.split(','))
            except ValueError:
                self.logger.error("Invalid admin IDs in environment variable STANDUP_BOT_ADMIN_IDS")

    def add_admin(self, user_id: int) -> None:
        """
        Add a user to the admin list.

        Args:
            user_id: User ID to add as admin.
        """
        self.admin_ids.add(user_id)
        self.logger.info(f"Added user {user_id} as admin")

    def remove_admin(self, user_id: int) -> None:
        """
        Remove a user from the admin list.

        Args:
            user_id: User ID to remove from admin list.
        """
        if user_id in self.admin_ids:
            self.admin_ids.remove(user_id)
            self.logger.info(f"Removed user {user_id} from admin list")

    def is_admin(self, user_id: int) -> bool:
        """
        Check if a user is an admin.

        Args:
            user_id: User ID to check.

        Returns:
            True if the user is an admin, False otherwise.
        """
        return user_id in self.admin_ids

    def handle_admin_command(self, message: Dict[str, Any]) -> bool:
        """
        Handle an admin command.

        Args:
            message: Zulip message object.

        Returns:
            True if the command was handled, False otherwise.
        """
        sender_id = message['sender_id']
        content = message['content'].strip()

        # Check if user is admin
        if not self.is_admin(sender_id):
            self.bot_handler.send_reply(message, "You don't have permission to use admin commands.")
            return True

        # Parse command
        if content.startswith('admin'):
            parts = content.split(maxsplit=2)
            if len(parts) < 2:
                self._send_admin_help(message)
                return True

            command = parts[1]
            args = parts[2] if len(parts) > 2 else ""

            # Handle different admin commands
            if command == 'help':
                self._send_admin_help(message)
            elif command == 'status':
                self._handle_status_command(message)
            elif command == 'backup':
                self._handle_backup_command(message, args)
            elif command == 'restore':
                self._handle_restore_command(message, args)
            elif command == 'clear-errors':
                self._handle_clear_errors_command(message)
            elif command == 'reset-rate-limits':
                self._handle_reset_rate_limits_command(message, args)
            elif command == 'restart-health-check':
                self._handle_restart_health_check_command(message)
            elif command == 'add-admin':
                self._handle_add_admin_command(message, args)
            elif command == 'remove-admin':
                self._handle_remove_admin_command(message, args)
            elif command == 'list-admins':
                self._handle_list_admins_command(message)
            elif command == 'debug':
                self._handle_debug_command(message, args)
            else:
                self.bot_handler.send_reply(message, f"Unknown admin command: {command}")

            return True

        return False

    def _send_admin_help(self, message: Dict[str, Any]) -> None:
        """Send help information for admin commands."""
        help_text = """
## Admin Commands

* `admin help` - Show this help message
* `admin status` - Show system status
* `admin backup [name]` - Create a backup (optional name)
* `admin restore <backup_file>` - Restore from a backup
* `admin clear-errors` - Clear error statistics
* `admin reset-rate-limits [key]` - Reset rate limits (optional key)
* `admin restart-health-check` - Restart health check server
* `admin add-admin <user_id>` - Add a user as admin
* `admin remove-admin <user_id>` - Remove a user from admin list
* `admin list-admins` - List all admin users
* `admin debug <component>` - Show debug information for a component
"""
        self.bot_handler.send_reply(message, help_text)

    def _handle_status_command(self, message: Dict[str, Any]) -> None:
        """Handle the status command."""
        status = {
            'time': datetime.now().isoformat(),
            'uptime': 'Unknown'
        }

        # Add monitoring status if available
        if self.monitoring:
            health_status = self.monitoring.get_health_status()
            status.update({
                'uptime': health_status.get('uptime', 'Unknown'),
                'status': health_status.get('status', 'Unknown'),
                'components': health_status.get('components', {}),
                'metrics': health_status.get('metrics', {})
            })

        # Add error stats if available
        if self.error_handler:
            status['errors'] = self.error_handler.get_error_stats()

        # Format status as markdown
        status_text = f"## System Status\n\n"
        status_text += f"* **Time**: {status['time']}\n"
        status_text += f"* **Uptime**: {status['uptime']}\n"

        if 'status' in status:
            status_text += f"* **Health**: {status['status']}\n\n"

        if 'components' in status:
            status_text += "### Component Health\n\n"
            for component, health in status['components'].items():
                status_text += f"* **{component}**: {health['status']}\n"
            status_text += "\n"

        if 'metrics' in status:
            status_text += "### Metrics\n\n"
            for metric, value in status['metrics'].items():
                status_text += f"* **{metric}**: {value}\n"
            status_text += "\n"

        if 'errors' in status and status['errors']:
            status_text += "### Recent Errors\n\n"
            for func, error_data in status['errors'].items():
                status_text += f"* **{func}**: {error_data['count']} errors, last: {error_data['last_error']}\n"

        self.bot_handler.send_reply(message, status_text)

    def _handle_backup_command(self, message: Dict[str, Any], args: str) -> None:
        """Handle the backup command."""
        if not self.backup_manager:
            self.bot_handler.send_reply(message, "Backup manager is not available.")
            return

        try:
            backup_name = args.strip() if args.strip() else None
            backup_file = self.backup_manager.create_backup(backup_name)
            self.bot_handler.send_reply(message, f"Backup created: {backup_file}")
        except Exception as e:
            self.logger.error(f"Error creating backup: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error creating backup: {str(e)}")

    def _handle_restore_command(self, message: Dict[str, Any], args: str) -> None:
        """Handle the restore command."""
        if not self.backup_manager:
            self.bot_handler.send_reply(message, "Backup manager is not available.")
            return

        backup_file = args.strip()
        if not backup_file:
            # List available backups
            backups = self.backup_manager.list_backups()
            if not backups:
                self.bot_handler.send_reply(message, "No backups available.")
                return

            backup_list = "## Available Backups\n\n"
            for i, backup in enumerate(backups):
                backup_list += f"{i+1}. **{backup['filename']}** ({backup['created']})\n"

            backup_list += "\nUse `admin restore <filename>` to restore a backup."
            self.bot_handler.send_reply(message, backup_list)
            return

        try:
            # Check if the backup file exists
            if not os.path.exists(backup_file):
                # Check if it's in the backup directory
                backup_path = os.path.join(self.backup_manager.backup_dir, backup_file)
                if os.path.exists(backup_path):
                    backup_file = backup_path
                else:
                    self.bot_handler.send_reply(message, f"Backup file not found: {backup_file}")
                    return

            # Confirm restore
            self.bot_handler.send_reply(message,
                f"Are you sure you want to restore from {backup_file}? This will overwrite all current data. "
                f"Reply with `admin confirm-restore {backup_file}` to proceed.")
        except Exception as e:
            self.logger.error(f"Error preparing restore: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error preparing restore: {str(e)}")

    def _handle_clear_errors_command(self, message: Dict[str, Any]) -> None:
        """Handle the clear-errors command."""
        if not self.error_handler:
            self.bot_handler.send_reply(message, "Error handler is not available.")
            return

        try:
            self.error_handler.reset_error_stats()
            self.bot_handler.send_reply(message, "Error statistics cleared.")
        except Exception as e:
            self.logger.error(f"Error clearing error stats: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error clearing error stats: {str(e)}")

    def _handle_reset_rate_limits_command(self, message: Dict[str, Any], args: str) -> None:
        """Handle the reset-rate-limits command."""
        if not self.rate_limiter:
            self.bot_handler.send_reply(message, "Rate limiter is not available.")
            return

        try:
            key = args.strip() if args.strip() else None
            self.rate_limiter.clear_limits(key)
            if key:
                self.bot_handler.send_reply(message, f"Rate limits cleared for key: {key}")
            else:
                self.bot_handler.send_reply(message, "All rate limits cleared.")
        except Exception as e:
            self.logger.error(f"Error resetting rate limits: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error resetting rate limits: {str(e)}")

    def _handle_restart_health_check_command(self, message: Dict[str, Any]) -> None:
        """Handle the restart-health-check command."""
        if not self.health_check_server:
            self.bot_handler.send_reply(message, "Health check server is not available.")
            return

        try:
            self.health_check_server.stop()
            time.sleep(1)  # Give it time to stop
            self.health_check_server.start()
            self.bot_handler.send_reply(message, "Health check server restarted.")
        except Exception as e:
            self.logger.error(f"Error restarting health check server: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error restarting health check server: {str(e)}")

    def _handle_add_admin_command(self, message: Dict[str, Any], args: str) -> None:
        """Handle the add-admin command."""
        try:
            user_id = int(args.strip())
            self.add_admin(user_id)
            self.bot_handler.send_reply(message, f"Added user {user_id} as admin.")
        except ValueError:
            self.bot_handler.send_reply(message, f"Invalid user ID: {args}")
        except Exception as e:
            self.logger.error(f"Error adding admin: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error adding admin: {str(e)}")

    def _handle_remove_admin_command(self, message: Dict[str, Any], args: str) -> None:
        """Handle the remove-admin command."""
        try:
            user_id = int(args.strip())
            self.remove_admin(user_id)
            self.bot_handler.send_reply(message, f"Removed user {user_id} from admin list.")
        except ValueError:
            self.bot_handler.send_reply(message, f"Invalid user ID: {args}")
        except Exception as e:
            self.logger.error(f"Error removing admin: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error removing admin: {str(e)}")

    def _handle_list_admins_command(self, message: Dict[str, Any]) -> None:
        """Handle the list-admins command."""
        try:
            if not self.admin_ids:
                self.bot_handler.send_reply(message, "No admin users configured.")
                return

            admin_list = "## Admin Users\n\n"
            for admin_id in sorted(self.admin_ids):
                admin_list += f"* {admin_id}\n"

            self.bot_handler.send_reply(message, admin_list)
        except Exception as e:
            self.logger.error(f"Error listing admins: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error listing admins: {str(e)}")

    def _handle_debug_command(self, message: Dict[str, Any], args: str) -> None:
        """Handle the debug command."""
        component = args.strip()

        if not component:
            self.bot_handler.send_reply(message, "Please specify a component to debug.")
            return

        try:
            if component == 'storage':
                self._debug_storage(message)
            elif component == 'database':
                self._debug_database(message)
            elif component == 'scheduler':
                self._debug_scheduler(message)
            elif component == 'monitoring':
                self._debug_monitoring(message)
            elif component == 'rate_limiter':
                self._debug_rate_limiter(message)
            elif component == 'backup':
                self._debug_backup(message)
            else:
                self.bot_handler.send_reply(message, f"Unknown component: {component}")
        except Exception as e:
            self.logger.error(f"Error debugging {component}: {str(e)}", exc_info=True)
            self.bot_handler.send_reply(message, f"Error debugging {component}: {str(e)}")

    def _debug_storage(self, message: Dict[str, Any]) -> None:
        """Debug storage component."""
        if not self.storage_manager:
            self.bot_handler.send_reply(message, "Storage manager is not available.")
            return

        # Get storage keys
        keys = list(self.storage_manager.storage.keys())

        debug_info = "## Storage Debug Info\n\n"
        debug_info += f"* **Storage Keys**: {len(keys)} keys\n"

        if hasattr(self.storage_manager, 'db_engine') and self.storage_manager.db_engine:
            debug_info += "* **Database**: Connected\n"

            # Get table info
            try:
                metadata = sa.MetaData()
                metadata.reflect(bind=self.storage_manager.db_engine)
                tables = list(metadata.tables.keys())

                debug_info += f"* **Tables**: {', '.join(tables)}\n"

                # Get row counts
                session = self.storage_manager.Session()
                try:
                    for table_name, table in metadata.tables.items():
                        count = session.query(sa.func.count()).select_from(table).scalar()
                        debug_info += f"  * **{table_name}**: {count} rows\n"
                finally:
                    session.close()
            except Exception as e:
                debug_info += f"* **Error**: {str(e)}\n"
        else:
            debug_info += "* **Database**: Not connected\n"

        self.bot_handler.send_reply(message, debug_info)

    def _debug_database(self, message: Dict[str, Any]) -> None:
        """Debug database component."""
        if not hasattr(self.storage_manager, 'db_engine') or not self.storage_manager.db_engine:
            self.bot_handler.send_reply(message, "Database is not configured.")
            return

        try:
            # Test database connection
            with self.storage_manager.db_engine.connect() as conn:
                result = conn.execute("SELECT 1").scalar()
                connection_ok = result == 1

            debug_info = "## Database Debug Info\n\n"
            debug_info += f"* **Connection**: {'OK' if connection_ok else 'Failed'}\n"
            debug_info += f"* **Engine**: {self.storage_manager.db_engine.name}\n"
            debug_info += f"* **URL**: {self.storage_manager.db_engine.url.render_as_string(hide_password=True)}\n"

            # Get database size
            if self.storage_manager.db_engine.name == 'postgresql':
                with self.storage_manager.db_engine.connect() as conn:
                    result = conn.execute("""
                        SELECT pg_size_pretty(pg_database_size(current_database()))
                    """).scalar()
                    debug_info += f"* **Database Size**: {result}\n"

            self.bot_handler.send_reply(message, debug_info)
        except Exception as e:
            self.bot_handler.send_reply(message, f"Error debugging database: {str(e)}")

    def _debug_scheduler(self, message: Dict[str, Any]) -> None:
        """Debug scheduler component."""
        # This would need to be implemented based on the scheduler implementation
        self.bot_handler.send_reply(message, "Scheduler debugging not implemented yet.")

    def _debug_monitoring(self, message: Dict[str, Any]) -> None:
        """Debug monitoring component."""
        if not self.monitoring:
            self.bot_handler.send_reply(message, "Monitoring is not available.")
            return

        health_status = self.monitoring.get_health_status()

        debug_info = "## Monitoring Debug Info\n\n"
        debug_info += f"* **Status**: {health_status.get('status', 'Unknown')}\n"
        debug_info += f"* **Uptime**: {health_status.get('uptime', 'Unknown')}\n\n"

        debug_info += "### Metrics\n\n"
        for metric, value in health_status.get('metrics', {}).items():
            debug_info += f"* **{metric}**: {value}\n"

        self.bot_handler.send_reply(message, debug_info)

    def _debug_rate_limiter(self, message: Dict[str, Any]) -> None:
        """Debug rate limiter component."""
        if not self.rate_limiter:
            self.bot_handler.send_reply(message, "Rate limiter is not available.")
            return

        debug_info = "## Rate Limiter Debug Info\n\n"

        # Get default limits
        debug_info += "### Default Limits\n\n"
        for key, (max_calls, period) in self.rate_limiter.default_limits.items():
            debug_info += f"* **{key}**: {max_calls} calls per {period} seconds\n"

        # Get custom limits
        if self.rate_limiter.custom_limits:
            debug_info += "\n### Custom Limits\n\n"
            for key, (max_calls, period) in self.rate_limiter.custom_limits.items():
                debug_info += f"* **{key}**: {max_calls} calls per {period} seconds\n"

        # Get active buckets
        if self.rate_limiter.buckets:
            debug_info += "\n### Active Rate Limit Buckets\n\n"
            for key, bucket in self.rate_limiter.buckets.items():
                if bucket:
                    status = self.rate_limiter.get_rate_limit_status(key.split(':')[0],
                                                                   key.split(':')[1] if ':' in key else None)
                    debug_info += f"* **{key}**: {status['used']}/{status['limit']} used, resets in {status['reset_seconds']:.1f}s\n"

        self.bot_handler.send_reply(message, debug_info)

    def _debug_backup(self, message: Dict[str, Any]) -> None:
        """Debug backup component."""
        if not self.backup_manager:
            self.bot_handler.send_reply(message, "Backup manager is not available.")
            return

        backups = self.backup_manager.list_backups()

        debug_info = "## Backup Debug Info\n\n"
        debug_info += f"* **Backup Directory**: {self.backup_manager.backup_dir}\n"
        debug_info += f"* **Backup Interval**: {self.backup_manager.backup_interval} hours\n"
        debug_info += f"* **Max Backups**: {self.backup_manager.max_backups}\n"
        debug_info += f"* **Available Backups**: {len(backups)}\n\n"

        if backups:
            debug_info += "### Recent Backups\n\n"
            for i, backup in enumerate(backups[:5]):  # Show only the 5 most recent
                size_mb = backup['size'] / (1024 * 1024)
                debug_info += f"{i+1}. **{backup['filename']}** ({backup['created']}, {size_mb:.2f} MB)\n"

        self.bot_handler.send_reply(message, debug_info)
