"""Cloudflare-style request filtering and security headers, enforced inside the app.

Mirrors the protections a Cloudflare zone gives (README "Security" lists the matching dashboard
rules), so the API is protected even when hit directly or deployed without Cloudflare:

  rule id           Cloudflare equivalent                      result
  ----------------  -----------------------------------------  -------------------------
  origin_lock       Transform Rule adds a secret header         403 ORIGIN_FORBIDDEN
  ip_allowlist      IP Access Rules (allow)                     403 REQUEST_BLOCKED
  ip_blocklist      IP Access Rules (block)                     403 REQUEST_BLOCKED
  url_too_long      WAF custom rule on http.request.uri length  414 URI_TOO_LONG
  method            WAF custom rule on http.request.method      405 METHOD_NOT_ALLOWED
  probe_path        WAF custom rule (/.env, /.git, wp-admin...) 404 NOT_FOUND
  scanner_ua        WAF custom rule / Bot Fight (sqlmap, nikto) 403 REQUEST_BLOCKED
  empty_ua          Browser Integrity Check (opt-in)            403 REQUEST_BLOCKED
  sig_*             Managed Rules / OWASP core (SQLi, XSS,      403 REQUEST_BLOCKED
                    traversal, Log4Shell) on URL + headers
  global_rate       Rate Limiting Rule (per IP)                 429 RATE_LIMITED

Request bodies are not pattern-matched (product descriptions and notes would cause false
positives); SQL injection is prevented by parameterised queries everywhere. /health is exempt
from everything but the IP rules so platform health checks keep working. Every block is logged
as a "security event" with rule id, IP, method and path (never query values or bodies).
"""
import hmac
import ipaddress
import re

from flask import current_app, request

from app.utils.rate_limit import client_ip, hit_limit
from app.utils.responses import error_response

ALLOWED_METHODS = {"GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS", "HEAD"}

_PROBE_PATH = re.compile(
    r"(^|/)(\.env|\.git|\.svn|\.hg|\.ds_store|\.aws|\.ssh|\.htaccess|\.htpasswd|wp-admin|wp-login|wp-content|"
    r"wp-includes|xmlrpc\.php|phpmyadmin|pma|cgi-bin|vendor/phpunit|server-status|actuator|solr|"
    r"boaform|hnap1|console)(/|$)|\.(php\d?|asp|aspx|jsp|cgi|bak|sql|sqlite|db|ini|log|swp)$",
    re.I,
)
_SCANNER_UA = re.compile(
    r"sqlmap|nikto|nmap|masscan|zgrab|acunetix|nessus|openvas|nuclei|wpscan|dirbuster|gobuster|ffuf|"
    r"feroxbuster|wfuzz|hydra|havij|netsparker|w3af|arachni|jaeles|commix|fimap|xsstrike|whatweb|"
    r"censysinspect|internet-measurement|zmeu|morfeus",
    re.I,
)
_SIGNATURES = (
    ("sig_traversal", re.compile(r"\.\.[/\\]|%2e%2e[%/\\]|/etc/(passwd|shadow)|c:\\windows\\", re.I)),
    ("sig_nullbyte", re.compile(r"\x00|%00")),
    ("sig_xss", re.compile(r"<\s*/?\s*(script|iframe|svg|object|embed)\b|javascript\s*:|\bon(error|load|"
                           r"mouseover|focus)\s*=|document\.cookie", re.I)),
    ("sig_sqli", re.compile(r"\bunion\b[\s(/*]+(all\s+)?select\b|'\s*(or|and)\s+'?\w+'?\s*=\s*'?\w+|"
                            r"\b(sleep|benchmark|pg_sleep)\s*\(|\bwaitfor\s+delay\b|"
                            r";\s*(drop|truncate|alter|delete|insert|update)\s+|\binformation_schema\b|"
                            r"\bload_file\s*\(|\binto\s+(out|dump)file\b|--\s*$|/\*!?\d*", re.I)),
    ("sig_log4shell", re.compile(r"\$\{\s*(jndi|lower|upper|env|sys|::-)", re.I)),
    ("sig_ssti", re.compile(r"\{\{\s*[^}]*(__class__|config|self|request)\b|\{%\s*(import|include)", re.I)),
)
# Headers worth scanning (commonly abused for injection / Log4Shell); never Authorization or cookies
_SCANNED_HEADERS = ("User-Agent", "Referer", "X-Forwarded-Host", "X-Api-Version")


def _networks(raw):
    nets = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            current_app.logger.error("edge-guard: ignoring invalid IP/CIDR %r", item)
    return nets


def _ip_in(ip_text, nets):
    try:
        ip = ipaddress.ip_address(ip_text)
    except ValueError:
        return False
    return any(ip in net for net in nets)


def _blocked(rule, status, code, message, ip):
    current_app.logger.warning("security-event rule=%s ip=%s method=%s path=%s", rule, ip, request.method,
                               request.path[:200])
    return error_response(message, status, code)


def _signature_hit():
    parts = [request.path]
    for key, values in request.args.lists():
        parts.append(key)
        parts.extend(values)
    for name in _SCANNED_HEADERS:
        value = request.headers.get(name)
        if value:
            parts.append(value)
    # Also check the raw (still-encoded) query string for encoded payloads such as %00 / %2e%2e
    parts.append(request.query_string.decode("latin-1", "replace"))
    text = "\n".join(parts)
    for rule, pattern in _SIGNATURES:
        if pattern.search(text):
            return rule
    return None


def edge_guard():
    cfg = current_app.config
    if not cfg.get("EDGE_GUARD_ENABLED", True):
        return None
    ip = client_ip()
    health = request.path.startswith("/health")

    allow = _networks(cfg.get("IP_ALLOWLIST"))
    if allow and not _ip_in(ip, allow):
        return _blocked("ip_allowlist", 403, "REQUEST_BLOCKED", "Access denied", ip)
    if _ip_in(ip, _networks(cfg.get("IP_BLOCKLIST"))):
        return _blocked("ip_blocklist", 403, "REQUEST_BLOCKED", "Access denied", ip)
    if health:
        return None

    secret = cfg.get("ORIGIN_AUTH_SECRET")
    if secret:
        supplied = request.headers.get(cfg.get("ORIGIN_AUTH_HEADER") or "X-Origin-Auth") or ""
        if not hmac.compare_digest(supplied.encode("utf-8"), secret.encode("utf-8")):
            return _blocked("origin_lock", 403, "ORIGIN_FORBIDDEN", "Direct origin access is not allowed", ip)

    max_url = int(cfg.get("MAX_URL_LENGTH") or 0)
    if max_url and len(request.full_path) > max_url:
        return _blocked("url_too_long", 414, "URI_TOO_LONG", "Request URL too long", ip)
    if request.method not in ALLOWED_METHODS:
        return _blocked("method", 405, "METHOD_NOT_ALLOWED", "Method not allowed", ip)
    if _PROBE_PATH.search(request.path):
        return _blocked("probe_path", 404, "NOT_FOUND", "Resource not found", ip)

    user_agent = (request.headers.get("User-Agent") or "").strip()
    if cfg.get("BLOCK_SCANNER_USER_AGENTS", True) and user_agent and _SCANNER_UA.search(user_agent):
        return _blocked("scanner_ua", 403, "REQUEST_BLOCKED", "Request blocked", ip)
    if cfg.get("BLOCK_EMPTY_USER_AGENT") and not user_agent and request.method != "OPTIONS":
        return _blocked("empty_ua", 403, "REQUEST_BLOCKED", "Request blocked", ip)

    rule = _signature_hit()
    if rule:
        return _blocked(rule, 403, "REQUEST_BLOCKED", "Request blocked", ip)

    allowed, retry_after = hit_limit("global", cfg.get("GLOBAL_RATE_LIMIT", 300),
                                     cfg.get("GLOBAL_RATE_WINDOW_SECONDS", 60))
    if not allowed:
        response = _blocked("global_rate", 429, "RATE_LIMITED", "Too many requests; slow down", ip)
        response.headers["Retry-After"] = str(retry_after)
        return response
    return None


_DOCS_CSP = ("default-src 'none'; script-src https://cdn.jsdelivr.net 'unsafe-inline'; "
             "style-src https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: https://cdn.jsdelivr.net; "
             "connect-src 'self'; font-src https://cdn.jsdelivr.net; frame-ancestors 'none'; base-uri 'none'")
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


def security_headers(response):
    """Headers only; status codes and bodies are never touched."""
    headers = response.headers
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    docs = request.path.startswith("/api/docs")
    headers.setdefault("Content-Security-Policy", _DOCS_CSP if docs else _API_CSP)
    prefix = (current_app.config.get("API_PREFIX") or "/api/v1").rstrip("/")
    if request.path.startswith(prefix) and "Cache-Control" not in headers:
        headers["Cache-Control"] = "no-store"  # tokens and personal data must not be cached by proxies
    if current_app.config.get("FLASK_ENV") == "production" or request.is_secure:
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def init_edge_guard(app):
    app.before_request(edge_guard)
    app.after_request(security_headers)
