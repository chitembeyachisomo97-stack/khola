"""
KHOLA for Windows - opens the online KHOLA website in its own app window.
The website address is read from site_url.txt (edit that file, then rebuild).
"""
import os
import sys
import webbrowser


def read_site_url():
    here = os.path.dirname(os.path.abspath(__file__))
    folders = [getattr(sys, "_MEIPASS", here), here, os.path.dirname(here), os.getcwd()]
    for folder in folders:
        path = os.path.join(folder, "site_url.txt")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                url = fh.read().strip()
            if url:
                return url
    raise SystemExit("site_url.txt not found")


def main():
    url = read_site_url()
    try:
        import webview  # pywebview: shows the site in a normal app window
    except ImportError:
        webbrowser.open(url)  # fallback: open in the default browser
        return
    webview.create_window("KHOLA", url, width=1000, height=760, min_size=(380, 600))
    webview.start()


if __name__ == "__main__":
    main()
