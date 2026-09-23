"""Read-only sandbox smoke test: authenticate, then optionally query one invoice."""

import argparse
import os
import sys

from piaozone import Piaozone
from piaozone.exceptions import PiaozoneError


def required(name):
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Set {name} before running the sandbox smoke test.")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-no", help="Existing original invoice request number")
    parser.add_argument("--seller-taxpayer-id", help="Seller tax ID for that request")
    args = parser.parse_args()
    if bool(args.serial_no) != bool(args.seller_taxpayer_id):
        parser.error("--serial-no and --seller-taxpayer-id must be given together")

    try:
        system_code = os.environ.get("PIAOZONE_SYSTEM_CODE")
        if args.serial_no and not system_code:
            raise ValueError("Set PIAOZONE_SYSTEM_CODE before querying an invoice.")
        with Piaozone(
            base_url=required("PIAOZONE_BASE_URL"),
            app_id=required("PIAOZONE_APP_ID"),
            app_secret=required("PIAOZONE_APP_SECRET"),
            account_id=required("PIAOZONE_ACCOUNT_ID"),
            user=required("PIAOZONE_USER"),
            user_type=os.environ.get("PIAOZONE_USER_TYPE", "UserName"),
            business_system_code=system_code or "__auth_only__",
            encryption=os.environ.get("PIAOZONE_ENCRYPTION", "base64"),
            aes_password=os.environ.get("PIAOZONE_AES_PASSWORD"),
        ) as client:
            client.access_token()
            print("SDK authentication: OK")
            if args.serial_no:
                result = client.invoice.query(args.serial_no, args.seller_taxpayer_id)
                print(f"Invoice query: success={result['success']}, errorCode={result['errorCode']}")
                return 0 if result["success"] else 1
    except (PiaozoneError, ValueError) as exc:
        print(f"Sandbox smoke test failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
