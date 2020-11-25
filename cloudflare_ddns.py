#!/usr/bin/env python
import configparser
import json
import sys
from argparse import (ArgumentParser, ArgumentTypeError)
from enum import Enum
from ipaddress import ip_address
from pathlib import Path

import requests
from requests import HTTPError

"""
usage: cloudflare_ddns.py [-h] config

Update Cloudflare DNS with public IP

positional arguments:
  config      path to config

optional arguments:
  -h, --help  show this help message and exit
"""

__version__ = "0.1"
__author__ = "Kieran O'Brien"

_IP_SERVICE_URL = "https://myip.dnsomatic.com/"

_CLOUDFLARE_URL = "https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
_HEADERS = {"Content-Type": "application/json"}
_PARAMS = {
    "type": "A",  # Request only A records
    "per_page": 1  # Request a single record (single page requested by default)
}


class Configuration(Enum):
    API_TOKEN = "api_token"
    ZONE_ID = "zone_id"
    DOMAIN = "domain"


def _parse_args():
    parser = ArgumentParser(description="Update Cloudflare DNS with public IP")
    parser.add_argument("config", type=_parse_config, help="path to config")
    return parser.parse_args()


def _parse_config(path_to_config):
    try:
        if not Path(path_to_config).is_file():
            raise ArgumentTypeError(f"File not found: {path_to_config}")

        parser = configparser.ConfigParser()
        parser.read(path_to_config)
        return {argument: parser["DEFAULT"][argument.value] for argument in Configuration}
    except KeyError as exception:
        raise ArgumentTypeError(f"Missing required argument: {exception}")
    except configparser.Error:
        raise ArgumentTypeError("Malformed config")


def _get_public_ip(service, url):
    try:
        response = service.get(url)
        response.raise_for_status()
        return str(ip_address(response.text))
    except HTTPError as exception:
        raise HTTPError(f"Request for public IP failed: {exception}")
    except ValueError as exception:
        raise ValueError(f"Invalid public IP: {exception}")


def _cloudflare_session(headers, params):
    cf_session = requests.Session()
    cf_session.headers.update(headers)
    cf_session.params = params
    return cf_session


def _parse_dns_records(payload):
    if payload["result_info"]["total_count"] == 1:
        return {"id": payload["result"][0]["id"], "ip": payload["result"][0]["content"]}
    else:
        raise ValueError("Found too many DNS records")


def _on_update_success(_):
    pass


def _validate_cloudflare_response(response, on_success):
    try:
        payload = response.json()
    except ValueError:
        raise ValueError(f"Cloudflare API response did not contain valid JSON: {response.content}")

    try:
        try:
            response.raise_for_status()
        except HTTPError as exception:
            raise HTTPError(f"{exception}: {payload['errors'][0]['message']}")

        if payload["success"]:
            return on_success(payload)
        else:
            raise ValueError(f"Operation failed: {payload['errors'][0]['message']}")
    except (KeyError, IndexError):
        raise ValueError(f"Cloudflare API response was malformed: {response.content}")


def _update_params_as_data(params, public_ip):
    data = dict(params)
    data.update({"content": public_ip, "ttl": 1})
    return json.dumps(data)


def _update_dns(session):
    with session:
        record_id, record_ip = _validate_cloudflare_response(session.get(_CLOUDFLARE_URL), _parse_dns_records).values()
        public_ip = _get_public_ip(requests, _IP_SERVICE_URL)

        if public_ip == record_ip:
            print("DNS already up to date")
            sys.exit()

        _validate_cloudflare_response(
            session.put(
                url=f"{_CLOUDFLARE_URL}/{record_id}",
                data=_update_params_as_data(session.params, public_ip)
            ),
            _on_update_success
        )
        print(f"Updated DNS for {session.params['name']}: {record_ip} -> {public_ip}")


if __name__ == "__main__":
    config = _parse_args().config

    # Update URL, headers and parameters with configured values
    _CLOUDFLARE_URL = _CLOUDFLARE_URL.format(zone_id=config[Configuration.ZONE_ID])
    _HEADERS["Authorization"] = f"Bearer {config[Configuration.API_TOKEN]}"
    _PARAMS["name"] = config[Configuration.DOMAIN]

    try:
        _update_dns(_cloudflare_session(_HEADERS, _PARAMS))
    except (requests.RequestException, ValueError) as e:
        sys.exit(e)
