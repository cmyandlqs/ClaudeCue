"""
Local HTTP server for receiving hook events.
Runs on localhost and provides an /event endpoint for POST requests.
"""
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock, Event
from queue import Queue, Empty
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Maximum request body size (64 KB - more than enough for hook events)
MAX_BODY_SIZE = 65536


class EventRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for /event endpoint.

    Uses instance attributes set during __init__ for thread safety.
    """

    def __init__(self, event_queue: Queue, event_callback: Optional[Callable],
                 *args, **kwargs):
        """Initialize with injected dependencies."""
        self.event_queue = event_queue
        self.event_callback = event_callback
        super().__init__(*args, **kwargs)

    def _set_response(self, status_code: int = 200) -> None:
        """Set HTTP response."""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/event":
            self._handle_event()
        elif self.path == "/health":
            self._handle_health()
        else:
            self._set_response(404)
            self.wfile.write(b'{"error": "Not found"}')

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/health":
            self._handle_health()
        else:
            self._set_response(404)
            self.wfile.write(b'{"error": "Not found"}')

    def _handle_event(self) -> None:
        """Handle incoming event POST request."""
        try:
            # Read request body with size limit
            # Validate and parse Content-Length header
            content_length_str = self.headers.get("Content-Length", "0")
            try:
                content_length = int(content_length_str)
            except ValueError:
                self._set_response(400)
                error_response = json.dumps({"error": f"Invalid Content-Length header: {content_length_str}"})
                self.wfile.write(error_response.encode("utf-8"))
                logger.warning(f"Invalid Content-Length received: {content_length_str}")
                return

            if content_length == 0:
                self._set_response(400)
                self.wfile.write(b'{"error": "Empty request body"}')
                return

            if content_length > MAX_BODY_SIZE:
                self._set_response(413)
                self.wfile.write(b'{"error": "Request body too large"}')
                logger.warning(f"Request body exceeds limit: {content_length}")
                return

            body = self.rfile.read(content_length)

            # Parse JSON
            try:
                event = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as e:
                self._set_response(400)
                error_response = json.dumps({"error": f"Invalid JSON: {e}"})
                self.wfile.write(error_response.encode("utf-8"))
                logger.warning(f"Invalid JSON received: {e}")
                return

            # Validate event has required fields
            if not isinstance(event, dict):
                self._set_response(400)
                self.wfile.write(b'{"error": "Event must be a JSON object"}')
                return

            # Add to queue
            if self.event_queue:
                self.event_queue.put(event)

            # Call callback if registered
            if self.event_callback:
                try:
                    self.event_callback(event)
                except Exception as e:
                    logger.error(f"Error in event callback: {e}")

            # Send success response
            self._set_response(200)
            self.wfile.write(b'{"status": "ok"}')
            logger.debug(f"Event received: {event.get('event_type', 'unknown')}")

        except Exception as e:
            logger.error(f"Error handling event: {e}")
            self._set_response(500)
            error_response = json.dumps({"error": "Internal server error"})
            self.wfile.write(error_response.encode("utf-8"))

    def _handle_health(self) -> None:
        """Handle health check requests."""
        self._set_response(200)
        self.wfile.write(b'{"status": "healthy", "service": "ccCue notifier"}')

    def log_message(self, format: str, *args) -> None:
        """Override to use Python logging instead of stderr."""
        logger.debug(f"HTTP: {format % args}")


def create_handler(event_queue: Queue, event_callback: Optional[Callable] = None):
    """Factory function to create handler with injected dependencies.

    Creates a subclass at runtime to capture dependencies in a thread-safe way.
    """
    class BoundEventHandler(EventRequestHandler):
        """Event handler with bound queue and callback."""

        def __init__(self, *args, **kwargs):
            super().__init__(event_queue, event_callback, *args, **kwargs)

    return BoundEventHandler


class NotifierServer:
    """
    HTTP server for receiving hook events.

    Runs on a background thread and exposes:
    - POST /event: Receive event notifications
    - GET /health: Health check endpoint
    """

    DEFAULT_PORT = 19527
    DEFAULT_HOST = "127.0.0.1"

    def __init__(self, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST):
        self.port = port
        self.host = host
        self.server: Optional[HTTPServer] = None
        self.event_queue: Queue = Queue()
        self.thread: Optional[Thread] = None
        self._lock = Lock()
        self._running = Event()  # Use Event instead of bool for thread safety

    def start(self, event_callback: Optional[Callable] = None) -> bool:
        """
        Start the HTTP server in a background thread.

        Args:
            event_callback: Optional callback function for incoming events

        Returns:
            True if started successfully, False otherwise
        """
        with self._lock:
            if self._running.is_set():
                logger.warning("Server already running")
                return True

            try:
                handler = create_handler(self.event_queue, event_callback)
                self.server = HTTPServer((self.host, self.port), handler)
                self.thread = Thread(target=self._serve_forever, daemon=True)
                self.thread.start()
                self._running.set()
                logger.info(f"Notifier server started on http://{self.host}:{self.port}")
                return True

            except OSError as e:
                logger.error(f"Failed to start server: {e}")
                return False

    def _serve_forever(self) -> None:
        """Run the server main loop."""
        if self.server:
            self.server.serve_forever()

    def stop(self) -> None:
        """Stop the HTTP server."""
        with self._lock:
            if not self._running.is_set():
                return

            if self.server:
                self.server.shutdown()
                self._running.clear()

                if self.thread:
                    self.thread.join(timeout=2)
                    self.thread = None

                logger.info("Notifier server stopped")

    def get_events(self):
        """
        Generator that yields pending events.

        Yields:
            Event dictionaries as they arrive
        """
        while True:
            try:
                yield self.event_queue.get_nowait()
            except Empty:
                break

    @property
    def is_running(self) -> bool:
        """Check if server is running (thread-safe)."""
        return self._running.is_set()

    @property
    def url(self) -> str:
        """Get the server's base URL."""
        return f"http://{self.host}:{self.port}"
