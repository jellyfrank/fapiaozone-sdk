import math
import secrets
import threading
import time
from urllib.parse import urlsplit

import requests
import simplejson

from .codec import Codec, dumps
from .exceptions import AuthenticationError, ProtocolError, TransportError
from .invoice import Invoice

MAX_RESPONSE_BYTES = 32 * 1024 * 1024


class Piaozone:
    """One independent account/session per client, with client.invoice business methods.

    The caller owns durable serial numbers and recovery. No request is retried,
    including on token rejection: only tokens are renewed before future requests.
    """

    def __init__(self, base_url, app_id, app_secret, account_id, user, business_system_code,
                 *, tenant_id="", user_type="UserName", encryption="base64", aes_password=None,
                 timeout=(10, 60), session=None):
        parsed = urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Configure an HTTPS tenant base URL without credentials, query or fragment.")
        if not all((app_id, app_secret, account_id, user, business_system_code)):
            raise ValueError("Missing Piaozone account configuration.")
        if user_type not in ("UserName", "Mobile"):
            raise ValueError("Unsupported Piaozone user type.")
        self.base_url = base_url.rstrip("/")
        self._app_id, self._app_secret = app_id, app_secret
        self._account_id, self._tenant_id = account_id, tenant_id
        self._user, self._user_type = user, user_type
        self.business_system_code = business_system_code
        self.timeout = timeout
        self._session = session if session is not None else requests.Session()
        self._owns_session = session is None
        self._token, self._expires = None, 0
        self._lock = threading.RLock()
        self.codec = Codec(encryption, aes_password)
        self.invoice = Invoice(self)

    def _post(self, path, body, token=None):
        try:
            with self._session.post(
                self.base_url + path, data=dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=UTF-8"},
                params={"access_token": token} if token else None,
                timeout=self.timeout, allow_redirects=False, stream=True,
            ) as response:
                if response.status_code != 200:
                    raise TransportError("Piaozone HTTP request failed; outcome is unconfirmed.")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise ProtocolError("Piaozone response exceeds size limit.")
                    chunks.append(chunk)
                result = simplejson.loads(b"".join(chunks).decode("utf-8"), use_decimal=True, allow_nan=False)
                if not isinstance(result, dict):
                    raise ProtocolError("Piaozone response must be an object.")
                return result
        except requests.RequestException:
            raise TransportError("Piaozone connection failed; query the original serial number.") from None
        except (UnicodeError, simplejson.JSONDecodeError):
            raise ProtocolError("Piaozone returned invalid JSON.") from None

    @staticmethod
    def _auth_data(result, key):
        data = result.get("data")
        if not isinstance(data, dict) or data.get("success") is not True or not isinstance(data.get(key), str) or not data[key]:
            raise AuthenticationError("Piaozone authentication failed; verify the account configuration.")
        return data

    def access_token(self):
        with self._lock:
            if self._token and time.time() < self._expires - 60:
                return self._token
            params = {"accountId": self._account_id, "tenantid": self._tenant_id}
            app = self._auth_data(self._post("/api/getAppToken.do", {
                **params, "appId": self._app_id, "appSecret": self._app_secret,
            }), "app_token")
            login = self._auth_data(self._post("/api/login.do", {
                **params, "apptoken": app["app_token"], "user": self._user, "usertype": self._user_type,
            }), "access_token")
            try:
                expires = float(login["expire_time"]) / 1000
                if not math.isfinite(expires) or expires <= time.time() + 60:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise AuthenticationError("Piaozone token expiry is invalid.") from None
            self._token, self._expires = login["access_token"], expires
            return self._token

    def call(self, interface_code, data, *, decode_data=True):
        """Single API call. requestId is a transport ID; serialNo remains caller-owned."""
        with self._lock:
            token = self.access_token()
            response = self._post("/kapi/app/sim/openApi", {
                "requestId": str(int(time.time() * 1000)) + f"{secrets.randbelow(1000):03d}",
                "businessSystemCode": self.business_system_code,
                "interfaceCode": interface_code, "data": self.codec.encode(data),
            }, token)
            if type(response.get("success")) is not bool or not isinstance(response.get("errorCode"), (str, int)):
                raise ProtocolError("Piaozone returned an invalid status envelope.")
            if response["success"] and str(response["errorCode"]) != "0":
                raise ProtocolError("Piaozone returned inconsistent status fields.")
            if response["success"] and decode_data and response.get("data") not in (None, ""):
                response["data"] = self.codec.decode(response["data"])
            if not response["success"]:
                # Unknown auth codes must not cause an automatic re-send of an invoice.
                self._token, self._expires = None, 0
            return response

    def close(self):
        if self._owns_session:
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
