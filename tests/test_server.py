"""
Tests for the notifier HTTP server.
"""
import json
import time
import urllib.request
import urllib.error
from sys import path

# Add parent directory to path for imports
path.insert(0, ".")

from notifier.server import NotifierServer


class TestNotifierServer:
    """Test NotifierServer class."""

    def test_server_initialization(self):
        """Test server initialization."""
        server = NotifierServer(port=19528)  # Use different port for tests
        assert server.port == 19528
        assert server.host == "127.0.0.1"
        assert not server.is_running
        assert server.url == "http://127.0.0.1:19528"

    def test_start_stop_server(self):
        """Test starting and stopping the server."""
        server = NotifierServer(port=19529)

        # Start server
        assert server.start() is True
        assert server.is_running

        # Give it a moment to start
        time.sleep(0.1)

        # Stop server
        server.stop()
        assert not server.is_running

    def test_health_endpoint(self):
        """Test the /health endpoint."""
        server = NotifierServer(port=19530)
        server.start()
        time.sleep(0.1)

        try:
            # Make request to health endpoint
            req = urllib.request.Request(
                "http://127.0.0.1:19530/health",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=1) as resp:
                assert resp.status == 200
                data = json.loads(resp.read().decode())
                assert data["status"] == "healthy"
                assert data["service"] == "ccCue notifier"
        finally:
            server.stop()

    def test_event_endpoint(self):
        """Test posting events to /event endpoint."""
        server = NotifierServer(port=19531)
        server.start()
        time.sleep(0.1)

        try:
            # Send event
            event_data = {
                "event_type": "test",
                "title": "Test Event",
                "message": "Test message"
            }
            data = json.dumps(event_data).encode("utf-8")

            req = urllib.request.Request(
                "http://127.0.0.1:19531/event",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1) as resp:
                assert resp.status == 200
                response = json.loads(resp.read().decode())
                assert response["status"] == "ok"

            # Check event was queued
            events = list(server.get_events())
            assert len(events) == 1
            assert events[0]["event_type"] == "test"

        finally:
            server.stop()

    def test_invalid_json_rejected(self):
        """Test that invalid JSON is rejected."""
        server = NotifierServer(port=19532)
        server.start()
        time.sleep(0.1)

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:19532/event",
                data=b"not json",
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                urllib.request.urlopen(req, timeout=1)
                assert False, "Expected HTTPError for invalid JSON"
            except urllib.error.HTTPError as e:
                assert e.code == 400
        finally:
            server.stop()

    def test_event_callback(self):
        """Test event callback functionality."""
        received_events = []

        def callback(event):
            received_events.append(event)

        server = NotifierServer(port=19533)
        server.start(event_callback=callback)
        time.sleep(0.1)

        try:
            # Send event
            event_data = {
                "event_type": "callback_test",
                "title": "Callback Test"
            }
            data = json.dumps(event_data).encode("utf-8")

            req = urllib.request.Request(
                "http://127.0.0.1:19533/event",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=1):
                pass

            # Give callback time to execute
            time.sleep(0.1)

            # Check callback was called
            assert len(received_events) == 1
            assert received_events[0]["event_type"] == "callback_test"

        finally:
            server.stop()

    def test_404_on_unknown_path(self):
        """Test 404 response for unknown paths."""
        server = NotifierServer(port=19534)
        server.start()
        time.sleep(0.1)

        try:
            req = urllib.request.Request(
                "http://127.0.0.1:19534/unknown",
                method="GET"
            )
            try:
                urllib.request.urlopen(req, timeout=1)
                assert False, "Expected HTTPError for unknown path"
            except urllib.error.HTTPError as e:
                assert e.code == 404
        finally:
            server.stop()
