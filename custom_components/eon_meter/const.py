DOMAIN = "eon_meter"

CONF_URL = "url"
CONF_TOKEN = "token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DATA_SOURCE = "data_source"

CONF_IMAP_HOST = "imap_host"
CONF_IMAP_PORT = "imap_port"
CONF_IMAP_USER = "imap_user"
CONF_IMAP_PASS = "imap_pass"
CONF_EMAIL_SUBJECT = "email_subject"

MODE_API = "API"
MODE_EMAIL = "Email"
MODE_BOTH = "API & Email"

DEFAULT_URL = "http://localhost:8000"
DEFAULT_SCAN_INTERVAL = 3600  # 1 hour
DEFAULT_DATA_SOURCE = MODE_EMAIL
DEFAULT_IMAP_PORT = 993
DEFAULT_EMAIL_SUBJECT = "Villanyóra Smart Meter Adatok"
