#!/usr/bin/env python3
import re
import sys
from datetime import datetime

html_file = 'driver/index.html'

# Read the HTML file
try:
    with open(html_file, 'r') as f:
        content = f.read()
except FileNotFoundError:
    print(f"Error: {html_file} not found")
    sys.exit(1)

# Generate timestamp in YYYYMMDD-HHMM format
timestamp = datetime.now().strftime('%Y%m%d-%H%M')

# Find and replace the style.css version
style_pattern = r'(style\.css\?v=)([^\s"\']+)'
style_match = re.search(style_pattern, content)

if not style_match:
    print("Error: style.css?v=... not found in index.html")
    sys.exit(1)

old_style_version = style_match.group(2)
print(f"Old style.css version: {old_style_version}")

# Find and replace the main.js version
js_pattern = r'(main\.js\?v=)([^\s"\']+)'
js_match = re.search(js_pattern, content)

if not js_match:
    print("Error: main.js?v=... not found in index.html")
    sys.exit(1)

old_js_version = js_match.group(2)
print(f"Old main.js version: {old_js_version}")

# Replace both versions
new_content = re.sub(style_pattern, r'\1' + timestamp, content)
new_content = re.sub(js_pattern, r'\1' + timestamp, new_content)

# Write back to file
with open(html_file, 'w') as f:
    f.write(new_content)

print(f"New version: {timestamp}")
print(f"Updated {html_file}")
