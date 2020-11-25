#!/usr/bin/env python
import unittest
from argparse import ArgumentTypeError
from unittest.mock import Mock

from requests import Response, HTTPError

from cloudflare_ddns import _parse_config, Configuration, _get_public_ip, _parse_dns_records, \
    _validate_cloudflare_response, _on_update_success, _update_params_as_data


class TestParseConfig(unittest.TestCase):

    def test_valid_config(self):
        config = _parse_config("test_data/valid.conf")
        self.assertDictEqual(config, {
            Configuration.API_TOKEN: "vyp77pEJnfqWLok8WTPo19PHSiF1zL3rYpox1dK0",
            Configuration.ZONE_ID: "fHHPMDIe2H81tUZBTTLKB8yLrvOhrV3lFo34bstI",
            Configuration.DOMAIN: "example.com"
        })

    def test_no_config(self):
        path_to_config = ""

        with self.assertRaises(ArgumentTypeError) as cm:
            _parse_config(path_to_config)

        self.assertEqual(str(cm.exception), f"File not found: {path_to_config}")

    def test_incomplete_config(self):
        with self.assertRaises(ArgumentTypeError) as cm:
            _parse_config("test_data/missing_required.conf")

        self.assertEqual(str(cm.exception), "Missing required argument: 'zone_id'")

    def test_malformed_config(self):
        with self.assertRaises(ArgumentTypeError) as cm:
            _parse_config("test_data/malformed.conf")

        self.assertEqual(str(cm.exception), "Malformed config")


class TestGetPublicIp(unittest.TestCase):

    def test_valid_ip(self):
        ip_address = "192.168.0.255"
        response = Response()
        response.status_code = 200
        response._content = bytes(ip_address, "UTF-8")
        service = Mock(get=Mock(return_value=response))
        self.assertEqual(_get_public_ip(service, ""), ip_address)

    def test_invalid_ip(self):
        response = Response()
        response.status_code = 200
        response._content = bytes("999.999.999.999", "UTF-8")
        service = Mock(get=Mock(return_value=response))

        with self.assertRaises(ValueError) as cm:
            _get_public_ip(service, "")

        self.assertEqual(str(cm.exception),
                         "Invalid public IP: '999.999.999.999' does not appear to be an IPv4 or IPv6 address")

    def test_failed_request(self):
        response = Response()
        response.status_code = 400
        service = Mock(get=Mock(return_value=response))

        with self.assertRaises(HTTPError) as cm:
            _get_public_ip(service, "")

        self.assertEqual(str(cm.exception), "Request for public IP failed: 400 Client Error: None for url: None")


class TestParseDnsRecords(unittest.TestCase):

    def test_single_record(self):
        record_id = "EDKaYKD5s5Hvuhk4mGDHd4Ovi9pdM4NMTwoF7t85"
        ip_address = "192.168.0.255"
        payload = {"result_info": {"total_count": 1}, "result": [{"id": record_id, "content": ip_address}]}
        self.assertDictEqual(_parse_dns_records(payload), {"id": record_id, "ip": ip_address})

    def test_multiple_records(self):
        with self.assertRaises(ValueError) as cm:
            _parse_dns_records({"result_info": {"total_count": 2}})

        self.assertEqual(str(cm.exception), "Found too many DNS records")

    def test_malformed_record(self):
        self.assertRaises(KeyError, _parse_dns_records, {"result_info": {"total_count": 1}})


class TestValidateCloudflareResponse(unittest.TestCase):

    def test_invalid_payload(self):
        response = Response()
        response.status_code = 200
        response._content = bytes("abc", "UTF-8")

        with self.assertRaises(ValueError) as cm:
            _validate_cloudflare_response(response, _on_update_success)

        self.assertEqual(str(cm.exception), "Cloudflare API response did not contain valid JSON: b'abc'")

    def test_operation_success_with_valid_payload(self):
        response = Response()
        response.status_code = 200
        response._content = bytes('{"success":true}', "UTF-8")
        self.assertIsNone(_validate_cloudflare_response(response, _on_update_success))

    def test_operation_failure_with_valid_payload(self):
        response = Response()
        response.status_code = 200
        response._content = bytes('{"success":false,"errors":[{"message":"Bad request"}]}', "UTF-8")

        with self.assertRaises(ValueError) as cm:
            _validate_cloudflare_response(response, _on_update_success)

        self.assertEqual(str(cm.exception), "Operation failed: Bad request")

    def test_request_failure_with_error_payload(self):
        response = Response()
        response.status_code = 400
        response._content = bytes('{"errors":[{"message":"Bad request"}]}', "UTF-8")

        with self.assertRaises(HTTPError) as cm:
            _validate_cloudflare_response(response, _on_update_success)

        self.assertEqual(str(cm.exception), "400 Client Error: None for url: None: Bad request")

    def test_request_failure_without_error_payload(self):
        response = Response()
        response.status_code = 400
        response._content = bytes('{}', "UTF-8")

        with self.assertRaises(ValueError) as cm:
            _validate_cloudflare_response(response, _on_update_success)

        self.assertEqual(str(cm.exception), "Cloudflare API response was malformed: b'{}'")


class TestUpdateParamsAsData(unittest.TestCase):

    def test_update_params(self):
        params = {"key": "value"}
        public_ip = "192.168.0.255"
        data = _update_params_as_data(params, public_ip)
        self.assertDictEqual(params, {"key": "value"})
        self.assertEqual(data, '{"key": "value", "content": "192.168.0.255", "ttl": 1}')


if __name__ == "__main__":
    unittest.main()
