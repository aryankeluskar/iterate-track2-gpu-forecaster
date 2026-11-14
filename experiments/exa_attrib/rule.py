import re
from urllib.parse import urlparse
from run_search import NAME, DOM
PRICE = re.compile(r"(pric|rate card|per hour|/hr|per gpu|\$\s?\d)", re.I)
# v0 (first version, fired on funding news): any price word and any change word in one passage
CHANGE0 = re.compile(r"(increas|rais|hike|cut|reduc|lower|new pric|effective|starting|updat|adjust|change|drop|discount|rise)", re.I)
# v1: a price noun and a change word within 60 characters of each other, in a passage that names a date or a number
PC = r"(pric(e|es|ing)|rates?|per[- ]hour|/hr)"
CH = r"(increas\w*|rise|rises|rising|hik\w*|cut|cuts|reduc\w*|lower\w*|drop\w*|chang\w*|adjust\w*|new|updat\w*|effective|going up|go up|goes from)"
V1 = re.compile(rf"({PC}.{{0,60}}{CH}|{CH}.{{0,60}}{PC})", re.I | re.S)
FUND = re.compile(r"(series [a-e]\b|funding|raises? \$|raised \$|credit facility|debt|financing|valuation|investors?)", re.I)
def own(h, prov):
    host = urlparse(h["url"]).netloc.lower()
    if any(host == d or host.endswith("." + d) for d in DOM[prov]): return True
    return NAME[prov].split()[0].lower() in (h["title"] or "").lower()
def passages(h): return h["highlights"] + [h["title"] or ""]
def strict0(h, prov):
    return own(h, prov) and any(PRICE.search(t) and CHANGE0.search(t) for t in passages(h))
def strict(h, prov):
    """v1: provider-owned page or provider named in title; one passage with price-noun near change-word, and the title is not a funding story"""
    if not own(h, prov) or FUND.search(h["title"] or ""): return False
    return any(V1.search(t) for t in passages(h))

MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE = re.compile(rf"((effective|starting|beginning|begins|from|as of|on|until|by)\s+(the\s+)?({MON}\s+\d{{1,2}}|\d{{1,2}}(st|nd|rd|th)?\s+(of\s+)?{MON}))", re.I)
def strict2(h, prov):
    """v2 (written after v1 fired on 10/10 controls): v1 and, in the same passage, a dated effective phrase and the word GPU or a GPU model"""
    if not own(h, prov) or FUND.search(h["title"] or ""): return False
    return any(V1.search(t) and DATE.search(t) and re.search(r"(gpu|h100|h200|b200|b300|a100|l40s|rtx)", t, re.I) for t in passages(h))
