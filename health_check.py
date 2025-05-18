import json
import threading
import time
import logging
from typing import Dict, Any, Callable, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

class HealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health check endpoints."""

    # Class variable to store the health check function
    health_check_func: Optional[Callable[[], Dict[str, Any]]] = None

    def do_GET(self):
        """Handle GET requests."""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        if path == '/health' or path == '/healthz':
            self._handle_health_check()
        elif path == '/metrics':
            self._handle_metrics()
        elif path == '/readiness':
            self._handle_readiness()
        elif path == '/liveness':
            self._handle_liveness()
        else:
            self.send_error(404, "Not Found")

    def _handle_health_check(self):
        """Handle health check endpoint."""
        if self.health_check_func:
            health_data = self.health_check_func()
            status_code = 200 if health_data.get('status') == 'healthy' else 503
            self._send_json_response(status_code, health_data)
        else:
            self._send_json_response(500, {'status': 'error', 'message': 'Health check function not configured'})

    def _handle_metrics(self):
        """Handle metrics endpoint."""
        if self.health_check_func:
            health_data = self.health_check_func()
            metrics = health_data.get('metrics', {})
            self._send_json_response(200, metrics)
        else:
            self._send_json_response(500, {'status': 'error', 'message': 'Health check function not configured'})

    def _handle_readiness(self):
        """Handle readiness probe endpoint."""
        if self.health_check_func:
            health_data = self.health_check_func()
            # A service is ready if all components are either healthy or degraded
            components = health_data.get('components', {})
            is_ready = True

            for component, status in components.items():
                if status.get('status') == 'unhealthy':
                    is_ready = False
                    break

            status_code = 200 if is_ready else 503
            self._send_json_response(status_code, {
                'status': 'ready' if is_ready else 'not_ready',
                'components': components
            })
        else:
            self._send_json_response(500, {'status': 'error', 'message': 'Health check function not configured'})

    def _handle_liveness(self):
        """Handle liveness probe endpoint."""
        if self.health_check_func:
            health_data = self.health_check_func()
            # A service is alive if it can respond, regardless of component health
            self._send_json_response(200, {
                'status': 'alive',
                'uptime': health_data.get('uptime', 'unknown')
            })
        else:
            # Even without a health check function, we can respond that we're alive
            self._send_json_response(200, {'status': 'alive'})

    def _send_json_response(self, status_code: int, data: Dict[str, Any]):
        """Send a JSON response with the given status code and data."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to use our logger instead of printing to stderr."""
        logger = logging.getLogger('standup_bot.health_check')
        logger.debug(f"{self.client_address[0]} - {format % args}")


class HealthCheckServer:
    """HTTP server for health check endpoints."""

    def __init__(self,
                 health_check_func: Callable[[], Dict[str, Any]],
                 host: str = '0.0.0.0',
                 port: int = 8080,
                 logger=None):
        """
        Initialize the health check server.

        Args:
            health_check_func: Function that returns health check data.
            host: Host to bind the server to.
            port: Port to bind the server to.
            logger: Optional logger instance.
        """
        self.host = host
        self.port = port
        self.logger = logger or logging.getLogger('standup_bot.health_check')

        # Set the health check function in the handler class
        HealthCheckHandler.health_check_func = health_check_func

        # Create the server
        self.server = HTTPServer((host, port), HealthCheckHandler)

        # Start server in a separate thread
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.running = False

    def start(self):
        """Start the health check server."""
        if not self.running:
            self.running = True
            self.server_thread.start()
            self.logger.info(f"Health check server started on {self.host}:{self.port}")

    def stop(self):
        """Stop the health check server."""
        if self.running:
            self.running = False
            self.server.shutdown()
            self.logger.info("Health check server stopped")

    def _run_server(self):
        """Run the server in a separate thread."""
        try:
            self.logger.info(f"Starting health check server on {self.host}:{self.port}")
            self.server.serve_forever()
        except Exception as e:
            self.logger.error(f"Error in health check server: {str(e)}", exc_info=True)
        finally:
            self.server.server_close()
            self.logger.info("Health check server closed")
