"""KHOLA settings - change business details here."""
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "khola.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

# Only people who know this code can register as admin.
# Change it before going online (or set the ADMIN_INVITE_CODE environment variable).
ADMIN_INVITE_CODE = os.environ.get("ADMIN_INVITE_CODE", "KHOLA-2026")

# No email server yet: the customer password reset link is shown on screen.
# Set to False once you add email sending.
SHOW_RESET_LINK = True

# Where customers send money
PAY_CHANNELS = {
    "Airtel Money": "0997353893",
    "TNM Mpamba": "0887764822",
    "FDH Bank": "149000019212",
}

# Contact details (footer + admin PIN restore)
ADMIN_CONTACT = "0997353893"
CONTACT_EMAIL = "chitembeyachisomo97@gmail.com"
CONTACT_WHATSAPP = "0997353893"

# High-res home photo presets for the admin, e.g. "https://.../chicken.jpg"
PRESET_PHOTOS = []

DEFAULT_PHOTO = ("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' "
                 "width='800' height='400'><rect width='100%' height='100%' fill='%23f4d9a8'/>"
                 "<text x='50%' y='50%' font-size='48' text-anchor='middle' fill='%23753'>"
                 "KHOLA Chicken Photo</text></svg>")

# First-time stock and prices (only used when the database is empty)
SEED_PRODUCTS = [
    ("Live Local Chicken", 50, [("Large", 17000), ("Medium", 14000), ("Standard", 10000)]),
    ("Live DuDu Chicken", 100, [("Jumbo Heavy", 12000), ("Standard Table", 10000),
                                ("Compact Roaster", 8000)]),
]
DEFAULT_BRAND = "KHOLA"
DEFAULT_MOTTO = "Lero tikhwasule!"


def load_secret_key():
    """Use SECRET_KEY env var if set, else create a random key once and keep it in secret.key"""
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    path = os.path.join(BASE_DIR, "secret.key")
    if not os.path.exists(path):
        with open(path, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(path) as fh:
        return fh.read().strip()
