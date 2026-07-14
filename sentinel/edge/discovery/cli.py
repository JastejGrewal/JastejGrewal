"""Site-survey CLI: `python -m sentinel.edge.discovery.cli --subnet 192.168.1.0/24`.

Prints one line per discovered endpoint (credentials redacted) and a tier
classification per host, matching the §3.3 site-survey checklist.
"""

from __future__ import annotations

import argparse
import ipaddress
import sys

from .prober import survey_site


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sentinel camera site survey")
    parser.add_argument("--subnet", help="CIDR to sweep for RTSP hosts, e.g. 192.168.1.0/24")
    parser.add_argument("--host", action="append", default=[], help="Explicit host(s) to probe")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--channels", type=int, default=4)
    args = parser.parse_args(argv)

    hosts = list(args.host)
    if args.subnet:
        network = ipaddress.ip_network(args.subnet, strict=False)
        if network.num_addresses > 1024:
            print("refusing to sweep more than 1024 addresses", file=sys.stderr)
            return 2
        hosts.extend(str(h) for h in network.hosts())

    reports = survey_site(
        hosts=hosts, user=args.user, password=args.password, channels=args.channels
    )
    found = 0
    for report in reports:
        if not report.endpoints:
            continue
        print(f"{report.host}  tier={report.tier}")
        for endpoint in report.endpoints:
            found += 1
            print(
                f"  ch{endpoint.channel:<2} [{endpoint.family}] "
                f"{endpoint.status:<13} {endpoint.redacted_url}"
            )
    if not found:
        print(
            "no digital endpoints found — if cameras exist here, this site is a "
            "tier (c) candidate: route to the partner analog-upgrade path"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
