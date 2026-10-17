#!/usr/bin/env python3
"""Build the shared ZIP table (launch_discovery/data/us_zips.json) from the GeoNames US postal code file.

    python3 enjoy_router/build_zip_table.py            # downloads https://download.geonames.org/export/zip/US.zip and writes the table
    python3 enjoy_router/build_zip_table.py US.zip     # or reads a copy you already downloaded

Run it once on a computer with internet (the cloud workspace cannot reach GeoNames). GeoNames data is licensed Creative Commons
Attribution 4.0; the credit is kept in launch_discovery/data/README.md. The table maps ZIP -> [state, latitude, longitude, place name]
for the 50 states and DC only (territories and military codes are left out). When a ZIP appears more than once the first row wins.
"""
import io, json, pathlib, sys, urllib.request, zipfile

OUT = pathlib.Path(__file__).resolve().parent / "launch_discovery" / "data" / "us_zips.json"
URL = "https://download.geonames.org/export/zip/US.zip"
STATES = frozenset("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())


def parse(text: str) -> dict:
    """GeoNames columns: country, postal code, place name, admin1 name, admin1 code (state), admin2 name, admin2 code, admin3 name,
    admin3 code, latitude, longitude, accuracy."""
    table = {}
    for line in text.splitlines():
        c = line.split("\t")
        if len(c) < 11 or c[0] != "US" or c[4] not in STATES:
            continue
        z = c[1].strip()
        if len(z) != 5 or not z.isdigit() or z in table:
            continue
        try:
            table[z] = [c[4], round(float(c[9]), 4), round(float(c[10]), 4), c[2][:80]]
        except ValueError:
            continue
    return table


def main(argv):
    raw = pathlib.Path(argv[1]).read_bytes() if len(argv) > 1 else urllib.request.urlopen(URL, timeout=60).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read("US.txt").decode("utf-8")
    table = parse(text)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(table, separators=(",", ":"), sort_keys=True))
    states = {row[0] for row in table.values()}
    print(f"wrote {len(table)} ZIP codes in {len(states)} states to {OUT}")
    if len(states) != 51 or len(table) < 30000:
        print("WARNING: expected 51 places (50 states and DC) and over 30,000 ZIPs; check the file")


if __name__ == "__main__":
    main(sys.argv)
