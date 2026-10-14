#!/usr/bin/env python3
"""Explicitly send one Brevo test email. Standard library only.

    python3 enjoy_router/run_smtp_test.py --send

The key is entered in a local terminal with echo disabled, never saved or logged.
Without --send this script cannot prompt for a key or connect to SMTP.
"""
from __future__ import annotations

import argparse
import getpass
import sys
import warnings

import smtp_transport

RECIPIENT = "toddbeetcher17@gmail.com"
SUBJECT = "Launch — Brevo SMTP test"
BODY = "This is the standalone Launch SMTP test. No registration was created.\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Send one Launch SMTP test email using Brevo.")
    parser.add_argument("--send", action="store_true", help="enable the real, single-message send")
    args = parser.parse_args(argv)
    if not args.send:
        print("No email sent. Use --send only when ready for the real test.")
        return 2
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        print("FAIL: a local interactive terminal is required; no email sent.")
        return 2

    key = None
    try:
        with warnings.catch_warnings():
            # getpass otherwise falls back to visible input on unsupported terminals.
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("Brevo SMTP key (hidden): ")
        smtp_transport.transport = smtp_transport.send_brevo
        result = smtp_transport.send(key, RECIPIENT, SUBJECT, BODY)
    except (getpass.GetPassWarning, EOFError):
        print("FAIL: hidden key entry unavailable; no email sent.")
        return 2
    except KeyboardInterrupt:
        print("UNKNOWN: interrupted; do not retry without checking whether a message arrived.")
        return 130
    except Exception:
        print("FAIL: local test error; details suppressed.")
        return 1
    finally:
        key = None  # release the reference; Python cannot guarantee secure memory erasure
        smtp_transport.transport = None

    if result.ok:
        print("PASS: Brevo accepted the test message. Check the inbox and spam folder for delivery.")
        return 0
    if result.code == "unknown":
        print("UNKNOWN: acceptance could not be confirmed. Check for delivery before retrying.")
        return 1
    print(f"FAIL: {result.code}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
