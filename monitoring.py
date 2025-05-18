import logging
import time
import os
import json
import threading
import socket
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import psutil

class Monitoring:
    """
    Monitoring and logging utilities for the Standup Bot.
    Provides methods for tracking metrics, health status, and system resources.
    """

    def __init__(self, logger=None, config=None):
        """
        Initialize the monitoring system.

        Args:
            logger: Optional logger instance. If not provided, a new one will be created.
            config: Optional configuration object.
        """
        self.logger = logger or logging.getLogger('standup_bot.monitoring')
        self.config = config
        self.metrics: Dict[str, Any] = {
            'bot_start_time': time.time(),
            'commands_processed': 0,
            'errors': 0,
            'api_calls': 0,
            'scheduled_tasks_executed': 0,
            'last_activity': time.time(),
            'response_times': [],
            'memory_usage': [],
            'cpu_usage': [],
        }
        self.component_health: Dict[str, Dict[str, Any]] = {
            'database': {'status': 'unknown', 'last_check': 0, 'details': None},
            'zulip_api': {'status': 'unknown', 'last_check': 0, 'details': None},
            'scheduler': {'status': 'unknown', 'last_check': 0, 'details': None},
            'storage': {'status': 'unknown', 'last_check': 0, 'details': None},
        }
        self.monitoring_interval = 60  # seconds
        self.max_response_times = 1000  # Keep only the last 1000 response times
        self.max_resource_metrics = 60  # Keep only the last 60 resource metrics (1 hour at 1 per minute)

        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

    def _monitoring_loop(self) -> None:
        """Background thread that collects system metrics periodically."""
        while True:
            try:
                # Collect system metrics
                self._collect_system_metrics()

                # Log periodic status
                self._log_status()

                # Sleep until next collection
                time.sleep(self.monitoring_interval)
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}", exc_info=True)
                time.sleep(self.monitoring_interval)

    def _collect_system_metrics(self) -> None:
        """Collect system metrics like CPU and memory usage."""
        try:
            # Get memory usage
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB

            # Get CPU usage
            cpu_percent = process.cpu_percent(interval=1.0)

            # Store metrics with timestamp
            timestamp = time.time()
            self.metrics['memory_usage'].append((timestamp, memory_mb))
            self.metrics['cpu_usage'].append((timestamp, cpu_percent))

            # Trim lists if they get too long
            if len(self.metrics['memory_usage']) > self.max_resource_metrics:
                self.metrics['memory_usage'] = self.metrics['memory_usage'][-self.max_resource_metrics:]
            if len(self.metrics['cpu_usage']) > self.max_resource_metrics:
                self.metrics['cpu_usage'] = self.metrics['cpu_usage'][-self.max_resource_metrics:]

        except Exception as e:
            self.logger.warning(f"Failed to collect system metrics: {str(e)}")

    def _log_status(self) -> None:
        """Log periodic status information."""
        uptime = time.time() - self.metrics['bot_start_time']
        uptime_str = str(timedelta(seconds=int(uptime)))

        # Calculate average response time
        avg_response_time = 0
        if self.metrics['response_times']:
            avg_response_time = sum(self.metrics['response_times']) / len(self.metrics['response_times'])

        # Get latest memory and CPU usage
        memory_usage = 0
        cpu_usage = 0
        if self.metrics['memory_usage']:
            memory_usage = self.metrics['memory_usage'][-1][1]
        if self.metrics['cpu_usage']:
            cpu_usage = self.metrics['cpu_usage'][-1][1]

        self.logger.info(
            f"Status: Uptime={uptime_str}, "
            f"Commands={self.metrics['commands_processed']}, "
            f"Errors={self.metrics['errors']}, "
            f"AvgResponseTime={avg_response_time:.2f}ms, "
            f"Memory={memory_usage:.1f}MB, "
            f"CPU={cpu_usage:.1f}%"
        )

    def track_command(self, command: str, execution_time: float) -> None:
        """
        Track a command execution.

        Args:
            command: The command that was executed.
            execution_time: Time taken to execute the command in milliseconds.
        """
        self.metrics['commands_processed'] += 1
        self.metrics['last_activity'] = time.time()
        self.metrics['response_times'].append(execution_time)

        # Trim response times list if it gets too long
        if len(self.metrics['response_times']) > self.max_response_times:
            self.metrics['response_times'] = self.metrics['response_times'][-self.max_response_times:]

    def track_error(self) -> None:
        """Track an error occurrence."""
        self.metrics['errors'] += 1

    def track_api_call(self) -> None:
        """Track a Zulip API call."""
        self.metrics['api_calls'] += 1

    def track_scheduled_task(self) -> None:
        """Track a scheduled task execution."""
        self.metrics['scheduled_tasks_executed'] += 1

    def update_component_health(self, component: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """
        Update the health status of a component.

        Args:
            component: The component name (e.g., 'database', 'zulip_api').
            status: The status ('healthy', 'degraded', 'unhealthy').
            details: Optional details about the health status.
        """
        if component in self.component_health:
            self.component_health[component] = {
                'status': status,
                'last_check': time.time(),
                'details': details or {}
            }

            # Log status changes
            self.logger.info(f"Component {component} health status: {status}")

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the overall health status of the bot.

        Returns:
            Dictionary with health status information.
        """
        # Calculate overall status based on component health
        overall_status = 'healthy'
        for component, health in self.component_health.items():
            if health['status'] == 'unhealthy':
                overall_status = 'unhealthy'
                break
            elif health['status'] == 'degraded' and overall_status != 'unhealthy':
                overall_status = 'degraded'

        # Calculate uptime
        uptime = time.time() - self.metrics['bot_start_time']
        uptime_str = str(timedelta(seconds=int(uptime)))

        # Get latest memory usage
        memory_usage = 0
        if self.metrics['memory_usage']:
            memory_usage = self.metrics['memory_usage'][-1][1]

        return {
            'status': overall_status,
            'uptime': uptime_str,
            'components': self.component_health,
            'metrics': {
                'commands_processed': self.metrics['commands_processed'],
                'errors': self.metrics['errors'],
                'memory_usage_mb': memory_usage,
                'last_activity': datetime.fromtimestamp(self.metrics['last_activity']).isoformat(),
            }
        }

    def check_database_health(self, db_engine) -> bool:
        """
        Check if the database is healthy.

        Args:
            db_engine: SQLAlchemy database engine.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            if not db_engine:
                self.update_component_health('database', 'unhealthy', {'error': 'No database engine'})
                return False

            # Execute a simple query to check connection
            with db_engine.connect() as connection:
                result = connection.execute("SELECT 1")
                if result.scalar() == 1:
                    self.update_component_health('database', 'healthy')
                    return True
                else:
                    self.update_component_health('database', 'unhealthy', {'error': 'Query returned unexpected result'})
                    return False
        except Exception as e:
            self.update_component_health('database', 'unhealthy', {'error': str(e)})
            self.logger.error(f"Database health check failed: {str(e)}", exc_info=True)
            return False

    def check_zulip_api_health(self, bot_handler) -> bool:
        """
        Check if the Zulip API is healthy.

        Args:
            bot_handler: Zulip bot handler.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            # Use a simple API call to check if the API is working
            # We'll use the storage API as a simple test
            test_key = 'health_check_test'
            test_value = {'timestamp': time.time()}

            # Try to store a value
            bot_handler.storage.put(test_key, test_value)

            # Try to retrieve the value
            retrieved = bot_handler.storage.get(test_key)

            if retrieved and 'timestamp' in retrieved:
                self.update_component_health('zulip_api', 'healthy')
                return True
            else:
                self.update_component_health('zulip_api', 'unhealthy', {'error': 'Failed to verify API storage'})
                return False
        except Exception as e:
            self.update_component_health('zulip_api', 'unhealthy', {'error': str(e)})
            self.logger.error(f"Zulip API health check failed: {str(e)}", exc_info=True)
            return False
