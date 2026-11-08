"""
KHOLA Standalone Windows Desktop Application.
Runs the Flask application locally inside a desktop window.
"""
import threading

import webview
from werkzeug.serving import make_server


def main():
    from app import app

    server = make_server("127.0.0.1", 0, app)
    port = server.server_port

    server_thread = threading.Thread(
        target=server.serve_forever,
        daemon=True
    )
    server_thread.start()

    try:
        webview.create_window(
            "KHOLA - Lero tikhwasule!",
            f"http://127.0.0.1:{port}",
            width=1100,
            height=780,
            min_size=(380, 600)
        )
        webview.start()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
