"""
This script is a simple helper to manually test the data extraction logic for
different real‑estate websites supported by the project.  It is intended to be
run from the root of the repository after installing the dependencies from
``requirements.txt``.

To use it, populate the ``URLS`` list below with detail page URLs from the
various domains you want to test (e.g. batdongsan.com.vn, alonhadat.com.vn,
chotot.com).  When executed, the script will loop through each URL, invoke
``extract_info_generic()`` from the crawler module, and print the parsed
results.  This allows you to quickly verify whether the current parsing rules
can successfully extract the title, price, area, description, image and
contact information from a given listing page.

For unsupported domains (such as chotot.com) the crawler will return a
structure indicating that the domain is not yet supported.  Use this output
to inform the development of new parser functions (e.g. ``parse_chotot``)
before adding the domain to ``SUPPORTED_DOMAINS`` in ``crawler.py``.

Example usage:

```bash
python test_extract.py
```

```console
Testing https://batdongsan.com.vn/ban-can-ho-chung-cu-tp-ho-chi-minh-pr123456
{'link': '...', 'title': 'Căn hộ ...', 'price': '3,5 tỷ', 'area': '85 m²',
 'description': '...', 'image': '...', 'contact': 'Nguyễn Văn A - 0901234567'}

Testing https://chotot.com/bat-dong-san ...
{'link': '...', 'title': '❓ Không hỗ trợ domain này', ...}
```
"""

from __future__ import annotations

from typing import List

from crawler import extract_info_generic

# TODO: Replace the example links below with real listing URLs you wish to
# validate.  For batdongsan.com.vn and alonhadat.com.vn, choose a detail
# page (the URL should contain a `-pr<id>` or `-<id>.html`).  For new
# domains like chotot.com, you can still include them here to see the
# unsupported message returned by the crawler.
URLS: List[str] = [
    # 'https://batdongsan.com.vn/ban-can-ho-chung-cu-duong-xyz-pr123456',
    # 'https://alonhadat.com.vn/ban-nha-duong-abc-hcm-123456.html',
    # 'https://www.chotot.com/ha-noi/mua-ban-nha-dat/123456789.htm',
]


def main() -> None:
    if not URLS:
        print(
            "No URLs specified. Edit test_extract.py and populate the URLS list "
            "with real listing links to test."
        )
        return

    for url in URLS:
        print(f"\nTesting {url}")
        try:
            info = extract_info_generic(url)
            # Pretty‑print the dictionary in a stable order for readability
            for key in ["title", "price", "area", "description", "image", "contact"]:
                print(f"{key:<12}: {info.get(key, '')}")
        except Exception as exc:
            print(f"Error while extracting {url}: {exc}")


if __name__ == "__main__":
    main()