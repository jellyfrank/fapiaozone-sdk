import base64
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import requests
import simplejson

from piaozone import Piaozone, AuthenticationError, ProtocolError, TransportError
from piaozone.codec import Codec, dumps


def response(value, status=200):
    result = Mock(status_code=status)
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.iter_content.return_value = [dumps(value).encode()]
    return result


def client(session=None, **kwargs):
    return Piaozone("https://tenant.example.test/tenant", "app", "SYNTHETIC-SECRET", "account", "user", "Odoo",
                    session=session or Mock(), **kwargs)


def auth(token="access", expires=9999999999999):
    return [response({"data": {"success": True, "app_token": "app-token"}}),
            response({"data": {"success": True, "access_token": token, "expire_time": expires}})]


def payload():
    return {"invoiceType": "02", "buyerName": "测试购方", "sellerName": "测试销方",
            "sellerTaxpayerId": "SYNTHETIC", "invoiceDetail": [{"amount": Decimal("0.10")} ]}


def test_token_cache_and_exact_wire_decimal():
    session = Mock()
    session.post.side_effect = auth() + [response({"success": True, "errorCode": "0", "data": "serial"}),
        response({"success": True, "errorCode": "0", "data": Codec().encode({"totalAmount": Decimal("0.10")})})]
    sdk = client(session)
    original = payload()
    sdk.invoice.issue_blue("stable-1", original)
    result = sdk.invoice.query("stable-1", "SYNTHETIC")
    assert result["data"]["totalAmount"] == Decimal("0.10")
    assert session.post.call_count == 4
    submit = session.post.call_args_list[2]
    wire = simplejson.loads(submit.kwargs["data"])
    data = base64.b64decode(wire["data"])
    assert b'"amount":0.10' in data
    assert b'"serialNo":"stable-1"' in data
    assert "serialNo" not in original
    assert len(wire["requestId"]) == 16
    assert submit.args[0] == "https://tenant.example.test/tenant/kapi/app/sim/openApi"
    assert submit.kwargs["allow_redirects"] is False
    login = simplejson.loads(session.post.call_args_list[1].kwargs["data"])
    assert login["usertype"] == "UserName"


def test_expired_token_refreshed_before_next_request():
    session = Mock()
    session.post.side_effect = auth("first") + auth("second")
    sdk = client(session)
    assert sdk.access_token() == "first"
    sdk._expires = 0
    assert sdk.access_token() == "second"


def test_accounts_never_share_session_or_token():
    one, two = client(), client()
    one._token = "private"
    assert two._token is None
    assert one.invoice is not two.invoice


def test_timeout_does_not_resubmit_or_leak_secrets():
    session = Mock()
    session.post.side_effect = auth() + [requests.Timeout("SECRET and access_token in URL")]
    with pytest.raises(TransportError) as error:
        client(session).invoice.issue_blue("stable-1", payload())
    assert session.post.call_count == 3
    assert "SECRET" not in str(error.value)


@pytest.mark.parametrize("code", ["10127", "30001", "UNRECOGNIZED", "401"])
def test_business_errors_return_without_resubmission(code):
    session = Mock()
    session.post.side_effect = auth() + [response({"success": False, "errorCode": code})]
    result = client(session).invoice.issue_blue("stable-1", payload())
    assert result["errorCode"] == code
    assert session.post.call_count == 3


@pytest.mark.parametrize("body", [{}, {"data": {"success": False}}, {"data": {"success": True, "app_token": ""}}])
def test_bad_auth_is_explicit(body):
    session = Mock()
    session.post.return_value = response(body)
    with pytest.raises(AuthenticationError):
        client(session).access_token()


@pytest.mark.parametrize("status", [302, 401, 500])
def test_http_errors_do_not_follow_redirects(status):
    session = Mock()
    session.post.return_value = response({}, status)
    with pytest.raises(TransportError):
        client(session).access_token()
    assert session.post.call_count == 1


@pytest.mark.parametrize("mode", ["base64", "aes"])
def test_codec_round_trip(mode):
    codec = Codec(mode, "synthetic-key")
    value = {"名称": "测试", "amount": Decimal("123456789012.34")}
    assert codec.decode(codec.encode(value)) == value


def test_aes_rejects_tampering_and_wrong_key():
    codec = Codec("aes", "synthetic-key")
    encrypted = codec.encode({"a": "b"})
    with pytest.raises(ProtocolError):
        Codec("aes", "wrong-key").decode(encrypted)
    raw = bytearray(base64.b64decode(encrypted))
    raw[-1] ^= 1
    with pytest.raises(ProtocolError):
        codec.decode(base64.b64encode(raw).decode())


def test_official_java_sha1prng_gcm_interoperability():
    # Generated with Java 8 SUN SHA1PRNG + AES/GCM/NoPadding, synthetic password.
    codec = Codec('aes', 'synthetic-key')
    assert base64.b64encode(codec._key).decode() == 'QRV4pRsmj5Vcn3z+fM22Qg=='
    vector = 'AAECAwQFBgcICQoLGuEesMoFwoz9IFDkmSlYGGeiA1vuby/hOAw8dtO2rM5e+94T5SmL/UCVK3JkYOo='
    value = {'amount': Decimal('0.10'), 'name': '测试'}
    assert codec.decode(vector) == value
    with patch('piaozone.codec.os.urandom', return_value=bytes(range(12))):
        assert codec.encode(value) == vector


def test_query_malformed_encoding_is_not_rejection():
    session = Mock()
    session.post.side_effect = auth() + [response({"success": True, "errorCode": "0", "data": "bad!"})]
    with pytest.raises(ProtocolError):
        client(session).invoice.query("stable", "seller")


@pytest.mark.parametrize("url", ["http://tenant.test", "https://user:pass@tenant.test", "https://tenant.test?token=x"])
def test_unsafe_configuration_rejected(url):
    with pytest.raises(ValueError):
        Piaozone(url, "app", "secret", "account", "user", "system")


def test_serial_validation_and_red_not_sent():
    sdk = client()
    with pytest.raises(ValueError):
        sdk.invoice.issue_blue("x" * 51, payload())
    with pytest.raises(ValueError):
        sdk.invoice.issue_blue("stable", {**payload(), "invoiceProperty": "1"})
    with pytest.raises(ValueError):
        sdk.invoice.issue_blue("stable", {**payload(), "serialNo": "different"})
    sdk._session.post.assert_not_called()
