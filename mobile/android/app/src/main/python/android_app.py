import os
import threading

_server = None
_server_thread = None


def start_server(data_dir, resource_dir):
    global _server, _server_thread

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(resource_dir, exist_ok=True)

    os.environ["KHOLA_DATA_DIR"] = data_dir
    os.environ["KHOLA_RESOURCE_DIR"] = resource_dir

    from werkzeug.serving import make_server
    from app import app

    _server = make_server(
        "127.0.0.1",
        0,
        app,
        threaded=True
    )

    port = _server.server_port

    _server_thread = threading.Thread(
        target=_server.serve_forever,
        daemon=True
    )
    _server_thread.start()

    return "http://127.0.0.1:" + str(port)
