from io import BytesIO
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest

from piaozone.documents import download_documents
from piaozone.exceptions import ProtocolError, TransportError


def session_for(raw, status=200):
    response = Mock(status_code=status)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [raw]
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.get.return_value = response
    return session


@pytest.mark.parametrize('url', ['https://evil.test/x', 'http://files.test/x',
                               'https://user:password@files.test/x', 'https://files.test:8080/x'])
def test_untrusted_file_url_never_requested(url):
    session = session_for(b'')
    with patch('piaozone.documents.requests.Session', return_value=session), pytest.raises(ProtocolError):
        download_documents({'invoiceFileUrl': url}, allowed_hosts=['files.test'])
    session.get.assert_not_called()


def test_pdf_no_tokens_or_redirects():
    session = session_for(b'%PDF-synthetic')
    with patch('piaozone.documents.requests.Session', return_value=session):
        files = download_documents({'invoiceFileUrl': 'https://files.test/file?signature=synthetic'}, allowed_hosts=['files.test'])
    assert files[0].data == b'%PDF-synthetic'
    assert files[0].name == 'invoice.pdf'
    assert session.get.call_args.kwargs['allow_redirects'] is False
    assert 'headers' not in session.get.call_args.kwargs
    assert session.trust_env is False


def test_xml_zip_extracted_in_memory():
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('../../not-written.xml', '<synthetic/>')
    session = session_for(stream.getvalue())
    with patch('piaozone.documents.requests.Session', return_value=session):
        files = download_documents({'xmlFileUrl': 'https://files.test/file'}, allowed_hosts=['files.test'])
    assert files[0].name == 'invoice.xml'
    assert files[0].data == b'<synthetic/>'


def test_oversized_file_and_zip_rejected():
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('one.xml', '<synthetic/>')
        archive.writestr('two.xml', '<synthetic/>')
    session = session_for(stream.getvalue())
    with patch('piaozone.documents.requests.Session', return_value=session), pytest.raises(ProtocolError):
        download_documents({'xmlFileUrl': 'https://files.test/file'}, allowed_hosts=['files.test'])
    session = session_for(b'x' * 100)
    with patch('piaozone.documents.MAX_FILE_BYTES', 50), patch('piaozone.documents.requests.Session', return_value=session), pytest.raises(ProtocolError):
        download_documents({'invoiceFileUrl': 'https://files.test/file'}, allowed_hosts=['files.test'])


def test_late_file_does_not_follow_redirect():
    session = session_for(b'', 302)
    with patch('piaozone.documents.requests.Session', return_value=session), pytest.raises(TransportError):
        download_documents({'invoiceFileUrl': 'https://files.test/file'}, allowed_hosts=['files.test'])
