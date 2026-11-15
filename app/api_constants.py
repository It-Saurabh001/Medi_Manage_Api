"""Client-facing constants shared by app-config, the OpenAPI spec and docs ."""

API_NAME = "Medi_Manage_Api"
API_VERSION = "1.0.0"

# R6 error codes with the suggested mobile-client reaction.
ERROR_CODES = {
    "VALIDATION_ERROR": "Show `fields` messages next to the inputs; fix and resend.",
    "NOT_FOUND": "Resource missing or not yours; refresh the list / go back.",
    "UNAUTHORIZED": "No/invalid credentials; send the user to login.",
    "TOKEN_EXPIRED": "Call POST /auth/refresh once, then retry; on failure go to login.",
    "TOKEN_INVALID": "Token revoked or malformed; clear tokens and go to login.",
    "FORBIDDEN": "Role not allowed; hide the action.",
    "ACCOUNT_BLOCKED": "Show 'account blocked, contact the pharmacy'; log out.",
    "ACCOUNT_NOT_APPROVED": "Show 'awaiting approval'; allow retry later.",
    "OUT_OF_STOCK": "Show available quantity from `fields.quantity`; let user reduce quantity.",
    "PRESCRIPTION_REQUIRED": "Ask for prescription upload and doctor name.",
    "PRESCRIPTION_NOT_VERIFIED": "Admin: verify the prescription before selling.",
    "INVALID_TRANSITION": "Order state changed; reload the order.",
    "CONFLICT": "Duplicate or state conflict; reload and show message.",
    "ALREADY_SOLD": "Order already sold; reload the order.",
    "BATCH_EXPIRED": "Pick a non-expired batch / correct the expiry date.",
    "UPGRADE_REQUIRED": "Block the UI and open the store page to update the app.",
    "RATE_LIMITED": "Too many attempts; wait or request a new OTP.",
    "PAYLOAD_TOO_LARGE": "File too large; compress or choose a smaller file.",
    "UNSUPPORTED_MEDIA_TYPE": "Wrong file/content type; use an allowed type.",
    "METHOD_NOT_ALLOWED": "Client bug: wrong HTTP method.",
    "INTERNAL_ERROR": "Show a generic error and allow retry.",
}

SUGGESTED_UNITS = ("strip", "bottle", "tube", "box", "vial", "sachet", "piece", "pack")
DEVICE_PLATFORMS = ("android", "ios")
