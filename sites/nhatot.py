# sites/nhatot.py
from bs4 import BeautifulSoup
import re
from .utils_dom import sel, sel1, text_or_empty as _txt

# Các selector bạn cung cấp (giữ nguyên) + một vài fallback ngắn gọn
_TITLE_SEL = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
              "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(2) > div > "
              "div > div > div.df0dbrp > div.d49myw8 > h1")
_PRICE_SEL = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
              "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(2) > div > "
              "div > div > div.plmkxo3 > div.r9vw5if > div > b")
_AREA_SEL = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
             "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(2) > div > "
             "div > div > div.plmkxo3 > div.r9vw5if > div > span.brnpcl3.t19tc1ar > strong")
_DESC_SEL = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
             "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(4) > div > "
             "div.d-lg-block.styles_adBodyCollapse__1Xvk7 > div:nth-child(2) > p")
_IMG_SEL  = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
             "div.c1uglbk9 > div.col-md-8.no-padding.d17dfbtj > div > div:nth-child(1) > div > "
             "div.sbxypvz > div.i12je7dy > span > img")

# Contact
_NAME_SEL_LONG = ("#__next > div > div.container.pty-container-detail > div.ct-detail.ao6jgem > div > "
                  "div.c1uglbk9 > div.col-md-4.no-padding.dtView.r1a38
