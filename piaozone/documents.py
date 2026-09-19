"""Bounded downloads from explicitly trusted invoice storage hosts."""
from dataclasses import dataclass
from io import BytesIO
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

import requests

from .exceptions import ProtocolError, TransportError

MAX_FILE_BYTES = 10 * 1024 * 1024
FILE_FIELDS = (("invoiceFileUrl", "pdf", "application/pdf"),
               ("ofdFileUrl", "ofd", "application/ofd"),
               ("xmlFileUrl", "xml", "application/xml"))


@dataclass(frozen=True)
class Document:
    name: str
    mimetype: str
    data: bytes


def download_documents(invoice, *, allowed_hosts, timeout=(10, 30)):
    """No auth tokens, redirects, implicit host trust or unbounded zip extraction."""
    hosts = {host.strip().lower() for host in allowed_hosts if host.strip()}
    documents = []
    with requests.Session() as session:
        session.trust_env = False  # Do not attach .netrc credentials to storage requests.
        for field, extension, mimetype in FILE_FIELDS:
            url = invoice.get(field)
            if not url:
                continue
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username
                    or parsed.password or parsed.fragment or parsed.port not in (None, 443)):
                raise ProtocolError("Invoice file URL is not on the configured HTTPS storage allowlist.")
            try:
                with session.get(url, timeout=timeout, allow_redirects=False, stream=True) as response:
                    if response.status_code != 200:
                        raise TransportError("Invoice document is not available yet.")
                    content, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise ProtocolError("Invoice document exceeds 10 MB.")
                        content.append(chunk)
                    raw = b"".join(content)
            except requests.RequestException:
                raise TransportError("Invoice document download failed.") from None
            if extension == "xml" and raw.startswith(b"PK"):
                try:
                    with ZipFile(BytesIO(raw)) as archive:
                        entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                        if (len(entries) != 1 or not entries[0].filename.lower().endswith(".xml")
                                or entries[0].file_size > MAX_FILE_BYTES):
                            raise ProtocolError("Expected one bounded XML invoice in the ZIP file.")
                        with archive.open(entries[0]) as stream:
                            raw = stream.read(MAX_FILE_BYTES + 1)
                except (BadZipFile, RuntimeError, OSError):
                    raise ProtocolError("Invalid invoice XML archive.") from None
            if not raw or len(raw) > MAX_FILE_BYTES:
                raise ProtocolError("Invoice document is empty or exceeds 10 MB.")
            if extension == "pdf" and not raw.startswith(b"%PDF-"):
                raise ProtocolError("Expected PDF invoice bytes.")
            if extension == "ofd" and not raw.startswith(b"PK"):
                raise ProtocolError("Expected OFD invoice archive.")
            if extension == "xml" and not raw.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"<"):
                raise ProtocolError("Expected XML invoice bytes.")
            documents.append(Document(f"invoice.{extension}", mimetype, raw))
    return documents
