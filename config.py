"""KHOLA settings for standalone desktop and mobile builds."""
import os
import sys
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Select a permanent, writable data directory.
if os.environ.get("KHOLA_DATA_DIR"):
    DATA_DIR = os.environ["KHOLA_DATA_DIR"]
elif getattr(sys, "frozen", False):
    DATA_DIR = os.path.join(
        os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
        "KHOLA"
    )
else:
    DATA_DIR = BASE_DIR

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "khola.db")

# Preserve the existing Termux upload location.
if not getattr(sys, "frozen", False) and not os.environ.get("KHOLA_DATA_DIR"):
    UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
else:
    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(UPLOAD_DIR, exist_ok=True)

ADMIN_INVITE_CODE = os.environ.get("ADMIN_INVITE_CODE", "KHOLA-2026")
SHOW_RESET_LINK = True

PAY_CHANNELS = {
    "Airtel Money": "0997353893",
    "TNM Mpamba": "0887764822",
    "FDH Bank": "149000019212",
}

ADMIN_CONTACT = "0997353893"
CONTACT_EMAIL = "chitembeyachisomo97@gmail.com"
CONTACT_WHATSAPP = "0997353893"

PRESET_PHOTOS = []

DEFAULT_PHOTO = (
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' "
    "width='800' height='400'><rect width='100%' height='100%' fill='%23f4d9a8'/>"
    "<text x='50%' y='50%' font-size='48' text-anchor='middle' fill='%23753'>"
    "KHOLA Chicken Photo</text></svg>"
)

SEED_PRODUCTS = [
    ("Live Local Chicken", 50, [
        ("Large", 17000),
        ("Medium", 14000),
        ("Standard", 10000)
    ]),
    ("Live DuDu Chicken", 100, [
        ("Jumbo Heavy", 12000),
        ("Standard Table", 10000),
        ("Compact Roaster", 8000)
    ]),
]

LOW_STOCK_LIMIT = 10
DEFAULT_BRAND = "KHOLA"
DEFAULT_MOTTO = "Lero tikhwasule!"


def load_secret_key():
    """Load or create a persistent application secret key."""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env

    path = os.path.join(DATA_DIR, "secret.key")

    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(secrets.token_hex(32))

    with open(path, encoding="utf-8") as fh:
        return fh.read().strip()
