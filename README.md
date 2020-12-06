# cloudflare-ddns

A simple script to keep Cloudflare DNS A records updated with your latest public IP address.

```
usage: cloudflare_ddns.py [-h] config

Update Cloudflare DNS with public IP

positional arguments:
  config      path to config
  
optional arguments:
  -h, --help  show this help message and exit
```

A valid configuration file looks like so:

```
[DEFAULT]
api_token = vyp77pEJnfqWLok8WTPo19PHSiF1zL3rYpox1dK0
zone_id = fHHPMDIe2H81tUZBTTLKB8yLrvOhrV3lFo34bstI
domain = example.com
```
