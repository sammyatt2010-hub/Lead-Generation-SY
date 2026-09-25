import base64
import hmac
import io
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

from bs4 import BeautifulSoup
from fpdf import FPDF
import pandas as pd
from pydantic import BaseModel, Field
import requests
import streamlit as st

# ==========================================
# 0. PASSWORD GATEWAY (STREAMLIT SECRETS)
# ==========================================


def check_password() -> bool:
    # Fail CLOSED: if the secret is missing or misconfigured, nobody gets in.
    try:
        configured_password = st.secrets["APP_PASSWORD"]
    except Exception:
        configured_password = None
    if not configured_password:
        st.set_page_config(page_title="Configuration Required", layout="centered")
        st.title("🔒 App Locked")
        st.error(
            "APP_PASSWORD is not configured in Streamlit Secrets, so access is"
            " blocked. Add it under App settings → Secrets."
        )
        return False

    def login_form():
        with st.form("Credentials"):
            st.text_input(
                "Enter Access Password", type="password", key="password"
            )
            st.form_submit_button("Log In", on_click=password_entered)

    def password_entered():
        if hmac.compare_digest(
            st.session_state.get("password", "").encode("utf-8"),
            str(configured_password).encode("utf-8"),
        ):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.set_page_config(page_title="Authentication Required", layout="centered")
    st.title("🔒 Restricted Access")
    st.caption("Please log in with the authorized password to continue.")
    login_form()

    if (
        "password_correct" in st.session_state
        and not st.session_state["password_correct"]
    ):
        st.error("😕 Incorrect password. Please try again.")

    return False


if not check_password():
    st.stop()

# ==========================================
# 1. VERTICALS, CRMS & PITCH PLAYBOOKS
# ==========================================

VERTICAL_PRESETS = {
    "Estate & Lettings Agents": {
        "sic_codes": ["68310"],
        "description": "Real estate agencies & letting operations",
        "search_hint": "Estate Agents",
        "crms": ["Street", "Alto", "Reapit", "Dezrez", "Jupix"],
        "primary_hook": "CRM Integration (Street / Alto / Reapit)",
        "fallback_greeting": "Lettings & Sales Team",
        "pitch_bullets": [
            "Screen pop-up of every client or landlord record the moment they call",
            "Automatic voice recording syncing directly to the property file",
            "Click to dial directly inside your CRM / property portal",
            "Every lead, missed call & call note tracked automatically",
        ],
        "default_cta": "Let me know how many phones or softphone users you have, and I'll send over a quote.",
    },
    "Dental Practices": {
        "sic_codes": ["86230"],
        "description": "Dental practice activities",
        "search_hint": "Dental Practice",
        "crms": ["Dentally", "EXACT", "Carestream R4"],
        "primary_hook": "PMS Integration (Dentally / EXACT / R4)",
        "fallback_greeting": "Practice Manager",
        "pitch_bullets": [
            "Patient records pop up on reception screens when the phone rings",
            "Calls log automatically against the right patient chart",
            "Missed calls are flagged instantly for follow up and recall retention",
            "Call recordings are stored compliantly against the patient file",
        ],
        "default_cta": "How many handsets does the practice currently use? I can send over a no obligation quote.",
    },
    "Solicitors & Legal Practices": {
        "sic_codes": ["69102"],
        "description": "Solicitors & legal service providers",
        "search_hint": "Solicitors",
        "crms": ["Clio", "LEAP", "Proclaim", "Actionstep"],
        "primary_hook": "Matter Management Integration (Clio / LEAP)",
        "fallback_greeting": "Practice Manager",
        "pitch_bullets": [
            "Dial straight from the active client or matter record",
            "Mobile & desktop softphone app so fee earners can take calls securely anywhere",
            "One unified system across reception, every fee earner and all branch offices",
            "Call recordings & billable duration synced back to the matter file",
        ],
        "default_cta": "Let me know which system you run and roughly how many users you have, and I'll send over a quote.",
    },
    "Accountants & Auditors": {
        "sic_codes": ["69201"],
        "description": "Accounting, bookkeeping & tax consultancy",
        "search_hint": "Accountants",
        "crms": ["Iris", "CCH", "TaxCalc", "Xero Practice Manager"],
        "primary_hook": "Client Portal & Time Tracking Integration",
        "fallback_greeting": "Practice Partner",
        "pitch_bullets": [
            "Client identification card pops on screen the moment they call",
            "Automatic call logging against client tax and year-end audit folders",
            "Seamless transfer between desk phones and laptop softphones for hybrid staff",
            "Consolidated line rental and cloud voice to reduce fixed telecom overheads",
        ],
        "default_cta": "Let me know your approximate team size and I can send over an indicative quote.",
    },
    "General Medical Clinics": {
        "sic_codes": ["86210"],
        "description": "General medical practice activities",
        "search_hint": "Clinic",
        "crms": ["EMIS Web", "SystmOne", "Semble", "Heydoc"],
        "primary_hook": "Clinical System Integration & Triage Routing",
        "fallback_greeting": "Clinic Manager",
        "pitch_bullets": [
            "Patient record screen-pop to accelerate inbound triage",
            "Automated call queueing & peak-time patient callback features",
            "Encrypted, compliant voice recordings stored per patient file",
            "Direct transfer lines between triage staff, clinicians, and administration",
        ],
        "default_cta": "How many lines or handsets do you operate? I can send over a no obligation overview.",
    },
}


class OfficerInfo(BaseModel):
    name: str
    role: str  # Friendly label, e.g. "Director"
    raw_role: str = ""  # Companies House value, e.g. "llp-designated-member"
    appointed_on: Optional[str] = None


class ScrapedLead(BaseModel):
    company_name: str
    company_number: Optional[str] = None
    sic_codes: List[str] = Field(default_factory=list)
    sector_guess: str = "General B2B"
    registered_address: Optional[str] = None
    website_url: Optional[str] = None
    phones_found: List[str] = Field(default_factory=list)
    emails_found: List[str] = Field(default_factory=list)
    officers: List[OfficerInfo] = Field(default_factory=list)
    site_meta_description: Optional[str] = None
    website_confidence: Optional[str] = None  # High / Medium / Low / Manual
    website_reasons: List[str] = Field(default_factory=list)
    discovery_notes: List[str] = Field(default_factory=list)
    other_emails: List[str] = Field(default_factory=list)  # Third-party addresses (agencies, regulators)
    pages_checked: List[str] = Field(default_factory=list)


# ==========================================
# 2. ENRICHMENT & SCRAPING ENGINE
# ==========================================


# ------------------------------------------------------------------
# Web discovery & extraction helpers
# ------------------------------------------------------------------

LEGAL_SUFFIX_WORDS = {
    "LTD", "LIMITED", "PLC", "LLP", "LP", "GROUP", "HOLDINGS", "UK", "(UK)",
    "CO", "COMPANY", "THE", "T/A", "INTERNATIONAL",
}

# Words too common to identify a firm on their own (kept for the full-name match)
GENERIC_NAME_WORDS = {
    "and", "the", "of", "dental", "dentist", "dentists", "practice", "practices",
    "surgery", "clinic", "clinics", "medical", "health", "healthcare", "care",
    "solicitors", "solicitor", "law", "legal", "lawyers", "partners", "partnership",
    "accountants", "accountancy", "accounting", "tax", "bookkeeping", "associates",
    "estate", "estates", "agents", "agency", "lettings", "letting", "property",
    "properties", "residential", "sales", "services", "consultants", "consultancy",
    "management", "uk", "ltd", "limited", "llp", "plc", "group", "holdings", "co",
}

# Directories, portals, social media, regulators and review sites — never a firm's own site.
BLOCKED_DOMAINS = {
    "company-information.service.gov.uk", "gov.uk", "companieshouse.gov.uk",
    "endole.co.uk", "duedil.com", "opencorporates.com", "companycheck.co.uk",
    "checkcompany.co.uk", "companiesintheuk.co.uk", "bizdb.co.uk", "companieslist.co.uk",
    "company-data.co.uk", "ukcompanieslist.com", "find-and-update.company-information.service.gov.uk",
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "pinterest.com", "wikipedia.org",
    "yell.com", "thomsonlocal.com", "scoot.co.uk", "192.com", "cylex-uk.co.uk",
    "freeindex.co.uk", "hotfrog.co.uk", "yelp.co.uk", "yelp.com", "trustpilot.com",
    "google.com", "google.co.uk", "bing.com", "duckduckgo.com", "maps.apple.com",
    "rightmove.co.uk", "zoopla.co.uk", "onthemarket.com", "primelocation.com",
    "allagents.co.uk", "getagent.co.uk", "homipi.co.uk", "propertymark.co.uk",
    "whatclinic.com", "doctify.com", "topdoctors.co.uk", "cqc.org.uk", "gdc-uk.org",
    "lawsociety.org.uk", "solicitors.lawsociety.org.uk", "sra.org.uk",
    "reviewsolicitors.co.uk", "solicitors.guru", "icaew.com", "accaglobal.com",
    "checkatrade.com", "ratedpeople.com", "bark.com", "mybuilder.com",
    "indeed.com", "indeed.co.uk", "glassdoor.co.uk", "reed.co.uk", "totaljobs.com",
    "zoominfo.com", "rocketreach.co", "apollo.io", "dnb.com", "kompass.com",
    "crunchbase.com", "bloomberg.com", "misterwhat.co.uk", "brownbook.net",
    "fyple.co.uk", "opendi.co.uk", "tuugo.co.uk", "infobel.com", "cybo.com",
    "n49.com", "businessmagnet.co.uk", "streetcheck.co.uk", "amazon.co.uk",
    "ebay.co.uk", "gumtree.com", "tripadvisor.co.uk", "118118.com", "ukphonebook.com",
}
# Blocked only as the exact domain (their subdomains can be real practice sites, e.g. xyzsurgery.nhs.uk)
BLOCKED_EXACT_ONLY = {"nhs.uk"}

FREE_MAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.co.uk", "outlook.com",
    "live.co.uk", "live.com", "yahoo.com", "yahoo.co.uk", "btinternet.com",
    "btconnect.com", "icloud.com", "me.com", "aol.com", "sky.com", "virginmedia.com",
    "talktalk.net", "nhs.net",
}

# Link hints for pages worth scraping, most useful first
CONTACT_PAGE_HINTS = [
    "contact", "get-in-touch", "get in touch", "getintouch", "find-us", "find us",
    "our-team", "our team", "meet-the-team", "meet the team", "team", "our-people",
    "people", "branches", "offices", "about",
]

JUNK_EMAIL_MARKERS = (
    "example.", "sentry", "wixpress", "domain.com", "yourname", "youremail",
    "email.com", "@2x", "noreply", "no-reply", "donotreply", "u003e", "godaddy",
    "wordpress", "schema.org", "@sentry", "@ingest", "test@",
)
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+'-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,24}")
PHONE_TEXT_RE = re.compile(
    r"(?:\+\s?44\s?(?:\(0\)\s?)?|0044\s?|\(?0)\d[\d \-\(\)]{7,14}\d"
)


def domain_of(url: str) -> Optional[str]:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = (urlparse(url).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host or None


def is_blocked_domain(domain: str) -> bool:
    domain = domain.lower()
    if domain in BLOCKED_EXACT_ONLY:
        return True
    return any(domain == b or domain.endswith("." + b) for b in BLOCKED_DOMAINS)


def domain_label(domain: str) -> str:
    """'www.hart-new-homes.co.uk' -> 'hartnewhomes'"""
    parts = domain.lower().split(".")
    for suffix_len in (3, 2, 1):  # handles .co.uk, .org.uk, .com etc
        tail = ".".join(parts[-suffix_len:])
        if tail in {"co.uk", "org.uk", "me.uk", "ltd.uk", "plc.uk", "nhs.uk", "net.uk"} and len(parts) > 2:
            return re.sub(r"[^a-z0-9]", "", parts[-3])
    return re.sub(r"[^a-z0-9]", "", parts[-2] if len(parts) >= 2 else parts[0])


def distinctive_name_tokens(company_name: str) -> List[str]:
    """'HART NEW HOMES (WALSALL) LIMITED' -> ['hart', 'new', 'homes', 'walsall']"""
    words = re.sub(r"[^a-z0-9 ]", " ", company_name.lower().replace("&", " and ")).split()
    words = [w for w in words if w.upper() not in LEGAL_SUFFIX_WORDS]
    distinct = [w for w in words if w not in GENERIC_NAME_WORDS]
    return distinct or words


def guess_domains(company_name: str) -> List[str]:
    """Likely domains straight from the name — a fallback when search engines block us."""
    words = [w for w in re.sub(r"[^a-z0-9& ]", " ", company_name.lower()).split()
             if w.upper() not in LEGAL_SUFFIX_WORDS and w != "&"]
    if not words:
        return []
    joined, hyphen = "".join(words), "-".join(words)
    distinct = [w for w in words if w not in GENERIC_NAME_WORDS]
    guesses = [f"{joined}.co.uk", f"{joined}.com", f"{hyphen}.co.uk", f"{joined}.uk"]
    if distinct and distinct != words:
        short = "".join(distinct)
        if len(short) >= 5:
            guesses.append(f"{short}.co.uk")
    return [g for g in dict.fromkeys(guesses) if len(g) <= 70]


def decode_cfemail(hex_string: str) -> Optional[str]:
    """Decodes Cloudflare's 'email protection' obfuscation."""
    try:
        data = bytes.fromhex(hex_string)
        key = data[0]
        return "".join(chr(b ^ key) for b in data[1:])
    except (ValueError, IndexError):
        return None


def clean_email(raw: str) -> Optional[str]:
    em = unquote(raw or "").strip().strip(".,;:()<>[]'\"").lower()
    em = em.split("?")[0]
    m = EMAIL_RE.fullmatch(em)
    if not m or len(em) > 80:
        return None
    if em.endswith(IMAGE_EXTS) or any(j in em for j in JUNK_EMAIL_MARKERS):
        return None
    return em


def extract_emails(soup: BeautifulSoup, html: str) -> Set[str]:
    found: Set[str] = set()
    # 1. mailto: links
    for a in soup.select('a[href^="mailto:" i]'):
        em = clean_email(a["href"].split(":", 1)[1])
        if em:
            found.add(em)
    # 2. Cloudflare-protected emails
    for el in soup.select("[data-cfemail]"):
        em = clean_email(decode_cfemail(el.get("data-cfemail", "")) or "")
        if em:
            found.add(em)
    for a in soup.select('a[href*="/cdn-cgi/l/email-protection#"]'):
        em = clean_email(decode_cfemail(a["href"].split("#", 1)[1]) or "")
        if em:
            found.add(em)
    # 3. Visible text, including "name [at] firm [dot] co.uk" style
    text = soup.get_text(" ")
    text = re.sub(r"\s*[\[\(\{]\s*at\s*[\]\)\}]\s*", "@", text, flags=re.I)
    text = re.sub(r"\s*[\[\(\{]\s*dot\s*[\]\)\}]\s*", ".", text, flags=re.I)
    # 4. Structured data (JSON-LD "email": "...")
    for script in soup.find_all("script", type="application/ld+json"):
        text += " " + (script.string or "")
    for raw in EMAIL_RE.findall(text):
        em = clean_email(raw)
        if em:
            found.add(em)
    return found


def normalise_uk_phone(raw: str) -> Optional[str]:
    """Any UK format -> standard display format, e.g. '+44 (0)1922 123456' -> '01922 123456'."""
    if not raw:
        return None
    raw = unquote(raw).replace("(0)", "")
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("0044"):
        digits = "0" + digits[4:]
    elif digits.startswith("44") and len(digits) == 12:
        digits = "0" + digits[2:]
    if not digits.startswith("0") or len(digits) not in (10, 11) or digits[1] not in "123578":
        return None
    d = digits
    if len(d) == 10:
        return f"{d[:5]} {d[5:]}"
    if d.startswith("02"):
        return f"{d[:3]} {d[3:7]} {d[7:]}"            # 020 7946 0000
    if d.startswith(("03", "08")):
        return f"{d[:4]} {d[4:7]} {d[7:]}"            # 0800 123 4567
    if d.startswith("07"):
        return f"{d[:5]} {d[5:]}"                     # 07700 900123
    if d[2] == "1" or d[3] == "1":
        return f"{d[:4]} {d[4:7]} {d[7:]}"            # 0121 234 5678
    return f"{d[:5]} {d[5:]}"                         # 01922 123456


def extract_phones(soup: BeautifulSoup, html: str) -> List[Tuple[str, int]]:
    """Returns (phone, weight). Clickable tel: links count more than plain text."""
    out: List[Tuple[str, int]] = []
    for a in soup.select('a[href^="tel:" i], a[href^="callto:" i]'):
        ph = normalise_uk_phone(a["href"].split(":", 1)[1])
        if ph:
            out.append((ph, 3))
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    for raw in PHONE_TEXT_RE.findall(soup.get_text(" ")):
        ph = normalise_uk_phone(raw)
        if ph:
            out.append((ph, 1))
    return out


def _describe_ch_error(resp: requests.Response) -> str:
    """Turns a Companies House HTTP error into a plain-English message."""
    code = resp.status_code
    if code == 401:
        return "Companies House rejected the API key (401). Check COMPANIES_HOUSE_KEY in Secrets."
    if code == 403:
        return "Companies House refused access (403). The key may not be a REST API key."
    if code == 404:
        return "No matching companies found (404)."
    if code == 416:
        return "Too many results requested. Narrow the search and try again."
    if code == 429:
        return "Companies House rate limit hit (600 requests / 5 mins). Wait a few minutes and retry."
    if code >= 500:
        return f"Companies House is having problems right now ({code}). Try again shortly."
    return f"Companies House returned an unexpected error ({code})."



class LeadEnricher:

    def __init__(self, ch_api_key: Optional[str] = None):
        self.ch_api_key = ch_api_key.strip() if ch_api_key else None
        self.base_url = "https://api.company-information.service.gov.uk"
        self.headers = self._get_auth_headers()
        self.web_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.web_headers)

    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.ch_api_key:
            return {}
        token = base64.b64encode(f"{self.ch_api_key}:".encode("utf-8")).decode(
            "utf-8"
        )
        return {"Authorization": f"Basic {token}"}

    def browse_vertical(
        self,
        sic_codes: List[str],
        location_keyword: Optional[str] = None,
        company_name_includes: Optional[str] = None,
        limit: int = 25,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Returns (results, error_message). error_message is None on success."""
        if not self.ch_api_key:
            return [], "No Companies House API key configured."

        url = f"{self.base_url}/advanced-search/companies"
        params: Dict[str, Any] = {
            "sic_codes": ",".join(sic_codes),
            "company_status": "active",
            "size": limit,
        }

        if location_keyword and location_keyword.strip():
            params["location"] = location_keyword.strip()

        if company_name_includes and company_name_includes.strip():
            params["company_name_includes"] = company_name_includes.strip()

        try:
            resp = requests.get(
                url, headers=self.headers, params=params, timeout=12
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                results = []
                for item in items:
                    addr = item.get("registered_office_address", {})
                    loc_parts = [
                        addr.get("locality"),
                        addr.get("postal_code"),
                    ]
                    location_str = ", ".join([p for p in loc_parts if p])
                    results.append(
                        {
                            "Company Name": item.get("company_name", ""),
                            "Company Number": item.get("company_number", ""),
                            "Incorporated": item.get(
                                "date_of_creation", "N/A"
                            ),
                            "Town / Postcode": location_str or "UK",
                            "Status": item.get("company_status", "").title(),
                            "Companies House": (
                                "https://find-and-update.company-information.service.gov.uk/company/"
                                + item.get("company_number", "")
                            ),
                        }
                    )
                return results, None
            if resp.status_code == 404:
                # Advanced search answers 404 when nothing matches.
                return [], None
            return [], _describe_ch_error(resp)
        except requests.exceptions.Timeout:
            return [], "Companies House didn't respond in time. Please try again."
        except requests.exceptions.RequestException as exc:
            return [], f"Couldn't reach Companies House ({exc.__class__.__name__})."
        except ValueError:
            return [], "Companies House returned an unreadable response."

    def get_company_details(self, company_number: str) -> Dict[str, Any]:
        if not self.ch_api_key:
            return {}
        url = f"{self.base_url}/company/{company_number}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return {}

    def get_officers(self, company_number: str) -> List[OfficerInfo]:
        if not self.ch_api_key:
            return []
        url = f"{self.base_url}/company/{company_number}/officers"
        officers = []
        try:
            resp = requests.get(
                url,
                headers=self.headers,
                params={"register_view": "true"},
                timeout=10,
            )
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    if not item.get("resigned_on"):
                        raw_role = (item.get("officer_role") or "").lower()
                        officers.append(
                            OfficerInfo(
                                name=item.get("name", "Unknown"),
                                role=format_role(raw_role),
                                raw_role=raw_role,
                                appointed_on=item.get("appointed_on"),
                            )
                        )
        except Exception:
            pass
        return officers

    # ------------------------------------------------------------------
    # WEBSITE DISCOVERY (search results + domain guesses, verified & scored)
    # ------------------------------------------------------------------

    def _fetch_html(self, url: str, timeout: int = 7) -> Optional[Tuple[str, str]]:
        """GETs a page. Returns (final_url_after_redirects, html) or None."""
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            ctype = resp.headers.get("Content-Type", "").lower()
            if resp.status_code == 200 and ("html" in ctype or not ctype):
                return resp.url, resp.text
        except requests.exceptions.RequestException:
            pass
        return None

    def _search_duckduckgo(self, query: str) -> Tuple[List[str], Optional[str]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        try:
            resp = self.session.get(url, timeout=7)
        except requests.exceptions.RequestException:
            return [], "DuckDuckGo unreachable"
        if resp.status_code != 200 or "anomaly" in resp.text.lower()[:5000]:
            return [], "DuckDuckGo blocked the request"
        soup = BeautifulSoup(resp.text, "html.parser")
        urls: List[str] = []
        for a in soup.select("a.result__a[href]"):
            href = a["href"]
            if "uddg=" in href:
                href = unquote(parse_qs(urlparse(href).query).get("uddg", [""])[0])
            if href.startswith("//"):
                href = "https:" + href
            urls.append(href)
        if not urls:  # Older markup: display URL only
            for span in soup.select(".result__url"):
                urls.append("https://" + span.get_text().strip())
        return urls, None

    def _search_bing(self, query: str) -> Tuple[List[str], Optional[str]]:
        url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=en-GB&cc=GB"
        try:
            resp = self.session.get(url, timeout=7)
        except requests.exceptions.RequestException:
            return [], "Bing unreachable"
        if resp.status_code != 200:
            return [], "Bing blocked the request"
        soup = BeautifulSoup(resp.text, "html.parser")
        urls: List[str] = []
        for a in soup.select("li.b_algo h2 a[href]"):
            href = a["href"]
            if "bing.com/ck/a" in href:  # Bing tracking wrapper: u=a1<base64url>
                u = parse_qs(urlparse(href).query).get("u", [""])[0]
                if u.startswith("a1"):
                    try:
                        b64 = u[2:] + "=" * (-len(u[2:]) % 4)
                        href = base64.urlsafe_b64decode(b64).decode("utf-8", "ignore")
                    except Exception:
                        continue
            urls.append(href)
        return urls, None

    def _score_candidate(
        self, domain: str, html: str, company_name: str,
        company_number: Optional[str], postcode: Optional[str], town: Optional[str],
    ) -> Tuple[int, List[str]]:
        """Scores how likely a site belongs to this company. Returns (score, reasons)."""
        score, reasons = 0, []
        tokens = distinctive_name_tokens(company_name)
        compact = "".join(tokens)
        label = domain_label(domain)

        # 1. Domain vs company name
        if compact and len(compact) >= 4 and (compact in label or (len(label) >= 5 and label in compact)):
            score += 45
            reasons.append("domain matches company name")
        else:
            hits = [t for t in tokens if len(t) >= 3 and t in label]
            if hits:
                score += min(15 * len(hits), 30)
                reasons.append(f"domain contains '{', '.join(hits)}'")

        soup = BeautifulSoup(html, "html.parser")
        title = (soup.title.get_text(" ", strip=True) if soup.title else "").lower()
        og = soup.find("meta", attrs={"property": "og:site_name"})
        if og and og.get("content"):
            title += " " + og["content"].lower()
        text = soup.get_text(" ", strip=True)
        text_l = text.lower()
        text_compact = re.sub(r"\s+", "", text_l)

        # 2. Page title / site name
        title_hits = [t for t in tokens if len(t) >= 3 and t in title]
        if title_hits:
            score += min(10 * len(title_hits), 20)
            reasons.append("name in page title")

        # 3. UK companies must show their registered number on their website
        if company_number:
            num = company_number.lstrip("0")
            if re.search(rf"(?<!\d)0*{re.escape(num)}(?!\d)", text_compact) and len(num) >= 5:
                score += 50
                reasons.append(f"company number {company_number} shown on site")

        # 4. Legal name / location on page
        legal = re.sub(r"\s+", " ", company_name.lower()).strip()
        if legal and legal in text_l:
            score += 20
            reasons.append("full legal name on site")
        if postcode and postcode.replace(" ", "").lower() in text_compact:
            score += 15
            reasons.append(f"registered postcode {postcode} on site")
        elif town and len(town) > 3 and town.lower() in text_l:
            score += 5
            reasons.append(f"mentions {town}")
        return score, reasons

    def auto_discover_website(
        self,
        company_name: str,
        location: Optional[str] = None,
        company_number: Optional[str] = None,
        postcode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Finds the firm's own website. Returns url, confidence, reasons and notes."""
        notes: List[str] = []
        clean_name = " ".join(w for w in re.sub(r"[^\w&' ]", " ", company_name).split()
                              if w.upper() not in LEGAL_SUFFIX_WORDS)
        query = f"{clean_name} {location or ''}".strip()

        # A. Search engines (DuckDuckGo, then Bing as a fallback)
        search_urls: List[str] = []
        for engine in (self._search_duckduckgo, self._search_bing):
            urls, err = engine(query)
            if err:
                notes.append(err)
            search_urls.extend(urls)
            if urls:
                break

        candidates: List[str] = []
        for u in search_urls:
            d = domain_of(u)
            if d and not is_blocked_domain(d) and d not in candidates:
                candidates.append(d)
        candidates = candidates[:6]

        # B. Domain guesses (works even when search engines block us)
        for guess in guess_domains(company_name):
            if guess not in candidates:
                candidates.append(guess)

        # C. Fetch & score candidates in parallel
        def check(domain: str):
            page = self._fetch_html(f"https://{domain}") or self._fetch_html(f"http://{domain}")
            if not page:
                return None
            final_url, html = page
            final_domain = domain_of(final_url) or domain
            if is_blocked_domain(final_domain):
                return None
            score, reasons = self._score_candidate(
                final_domain, html, company_name, company_number, postcode, location
            )
            return final_url, final_domain, score, reasons

        results = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for res in pool.map(check, candidates):
                if res:
                    results.append(res)

        if not results:
            notes.append("No candidate website responded")
            return {"url": None, "confidence": None, "reasons": [], "notes": notes}

        results.sort(key=lambda r: r[2], reverse=True)
        final_url, final_domain, score, reasons = results[0]
        if score < 35:
            notes.append(f"Best candidate {final_domain} scored too low to trust")
            return {"url": None, "confidence": None, "reasons": reasons, "notes": notes,
                    "rejected": final_domain}

        confidence = "High" if score >= 80 else "Medium" if score >= 55 else "Low"
        parsed = urlparse(final_url)
        return {
            "url": f"{parsed.scheme}://{parsed.netloc}",
            "confidence": confidence,
            "reasons": reasons,
            "notes": notes,
        }

    # ------------------------------------------------------------------
    # CONTACT SCRAPING (contact/about/team pages, hidden emails, clean phones)
    # ------------------------------------------------------------------

    def _find_contact_pages(self, soup: BeautifulSoup, root: str) -> List[str]:
        root_host = domain_of(root)
        ranked: List[Tuple[int, str]] = []
        for a in soup.find_all("a", href=True):
            href = urljoin(root + "/", a["href"].strip())
            if not href.startswith("http") or domain_of(href) != root_host:
                continue
            path_and_text = (urlparse(href).path + " " + a.get_text(" ", strip=True)).lower()
            for rank, hint in enumerate(CONTACT_PAGE_HINTS):
                if hint in path_and_text:
                    clean = href.split("#")[0].rstrip("/")
                    if clean != root.rstrip("/"):
                        ranked.append((rank, clean))
                    break
        seen, pages = set(), []
        for _, url in sorted(ranked):
            if url not in seen:
                seen.add(url)
                pages.append(url)
        return pages[:4]

    def scrape_contact_channels(self, base_url: str) -> Dict[str, Any]:
        empty = {"emails": [], "other_emails": [], "phones": [], "description": "",
                 "resolved_url": None, "pages_checked": []}
        if not base_url:
            return empty
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"

        home = self._fetch_html(base_url)
        if not home and base_url.startswith("https://"):
            home = self._fetch_html("http://" + base_url[len("https://"):])
        if not home:
            return {**empty, "resolved_url": base_url}

        final_url, home_html = home
        parsed = urlparse(final_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        site_domain = domain_of(root)
        home_soup = BeautifulSoup(home_html, "html.parser")

        extra_pages = self._find_contact_pages(home_soup, root)
        if not extra_pages:
            extra_pages = [urljoin(root, p) for p in ("/contact", "/contact-us", "/about", "/about-us")]

        pages_html = [(final_url, home_html)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            for url, page in zip(extra_pages, pool.map(self._fetch_html, extra_pages)):
                if page:
                    pages_html.append((page[0], page[1]))

        email_hits: Dict[str, int] = {}
        phone_scores: Dict[str, int] = {}
        description = ""

        for _, html in pages_html:
            soup = BeautifulSoup(html, "html.parser")
            if not description:
                for attrs in ({"name": "description"}, {"property": "og:description"}):
                    tag = soup.find("meta", attrs=attrs)
                    if tag and tag.get("content"):
                        description = tag["content"].strip()
                        break
            for em in extract_emails(soup, html):
                email_hits[em] = email_hits.get(em, 0) + 1
            for ph, weight in extract_phones(soup, html):
                phone_scores[ph] = phone_scores.get(ph, 0) + weight

        own, freemail, other = [], [], []
        for em in email_hits:
            dom = em.split("@", 1)[1]
            if dom == site_domain or dom.endswith("." + site_domain) or site_domain.endswith("." + dom):
                own.append(em)
            elif dom in FREE_MAIL_DOMAINS:
                freemail.append(em)
            else:
                other.append(em)

        phones = sorted(phone_scores, key=lambda p: (-phone_scores[p], p))[:5]
        return {
            "emails": sorted(own) + sorted(freemail),
            "other_emails": sorted(other),
            "phones": phones,
            "description": description,
            "resolved_url": root,
            "pages_checked": [u for u, _ in pages_html],
        }

    def enrich_selected_company(
        self,
        company_number: str,
        sector_name: str,
        manual_website: Optional[str] = None,
    ) -> ScrapedLead:
        ch_data = self.get_company_details(company_number)
        company_name = ch_data.get("company_name", company_number)

        address_dict = ch_data.get("registered_office_address", {})
        address_parts = [
            address_dict.get(k)
            for k in [
                "premises",
                "address_line_1",
                "locality",
                "region",
                "postal_code",
            ]
            if address_dict.get(k)
        ]
        registered_address = (
            ", ".join(address_parts) if address_parts else None
        )
        town = address_dict.get("locality")
        postcode = address_dict.get("postal_code")

        officers = self.get_officers(company_number)

        target_website = manual_website.strip() if manual_website else None
        discovery: Dict[str, Any] = {"confidence": "Manual", "reasons": ["entered by you"], "notes": []}
        if not target_website:
            discovery = self.auto_discover_website(
                company_name,
                location=town or postcode,
                company_number=company_number,
                postcode=postcode,
            )
            target_website = discovery.get("url")

        site_contacts = (
            self.scrape_contact_channels(target_website)
            if target_website
            else {"emails": [], "other_emails": [], "phones": [], "description": "",
                  "resolved_url": None, "pages_checked": []}
        )
        notes = list(discovery.get("notes", []))
        if target_website and not site_contacts.get("pages_checked"):
            notes.append("Website didn't respond when scraping contacts")

        return ScrapedLead(
            company_name=company_name,
            company_number=company_number,
            sic_codes=ch_data.get("sic_codes", []),
            sector_guess=sector_name,
            registered_address=registered_address,
            website_url=site_contacts.get("resolved_url") or target_website,
            phones_found=site_contacts["phones"],
            emails_found=site_contacts["emails"],
            officers=officers,
            site_meta_description=site_contacts["description"],
            website_confidence=discovery.get("confidence") if target_website else None,
            website_reasons=discovery.get("reasons", []),
            discovery_notes=notes,
            other_emails=site_contacts.get("other_emails", []),
            pages_checked=site_contacts.get("pages_checked", []),
        )


# ==========================================
# 3. PITCH SYNTHESIZER & PDF BUILDER
# ==========================================


def sanitize_pdf_text(text: str) -> str:
    """Replaces Unicode bullets, smart quotes, and dashes with Latin-1 equivalents for FPDF."""
    if not text:
        return ""
    replacements = {
        "\u2022": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "—": "-",
        "–": "-",
        "•": "-",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", errors="replace").decode("latin-1")


# Companies House officer_role values, best decision-maker first.
# Secretaries and all "corporate-*" roles (companies, not people) are excluded.
DECISION_MAKER_ROLES = [
    "director",
    "llp-designated-member",
    "llp-member",
    "managing-officer",
    "member",
]

ROLE_LABELS = {
    "director": "Director",
    "llp-designated-member": "Designated Member (LLP)",
    "llp-member": "Member (LLP)",
    "managing-officer": "Managing Officer",
    "member": "Member",
    "secretary": "Company Secretary",
    "nominee-director": "Nominee Director",
}

NAME_TITLES = {"mr", "mrs", "ms", "miss", "dr", "sir", "dame", "prof", "professor", "lord", "lady", "rev"}


def format_role(raw_role: str) -> str:
    raw_role = (raw_role or "").strip().lower()
    return ROLE_LABELS.get(raw_role, raw_role.replace("-", " ").title() or "Officer")


def first_name_from_officer(raw_name: str) -> Optional[str]:
    """Companies House lists people as 'SURNAME, Forename Middle'.
    Returns the forename, e.g. 'BYWATER, Paul James' -> 'Paul'."""
    if not raw_name:
        return None
    if "," in raw_name:
        forenames = raw_name.split(",", 1)[1]
    else:
        forenames = raw_name  # Rare 'Paul BYWATER' style: first word is the forename
    for token in forenames.replace(".", " ").split():
        clean = re.sub(r"[^A-Za-z'\-]", "", token)
        if clean and clean.lower() not in NAME_TITLES and len(clean) > 1:
            return "-".join(p[:1].upper() + p[1:].lower() for p in clean.split("-"))
    return None


def pick_decision_maker(officers: List["OfficerInfo"]) -> Optional["OfficerInfo"]:
    """Chooses the most senior active person (directors first, longest-serving first)."""
    for wanted in DECISION_MAKER_ROLES:
        matches = [o for o in officers if o.raw_role == wanted]
        if matches:
            return sorted(matches, key=lambda o: o.appointed_on or "9999")[0]
    return None


GENERIC_EMAIL_PREFIXES = {
    "info", "information", "enquiries", "enquiry", "enq", "sales", "lettings", "letting",
    "rentals", "lets", "office", "admin", "administration", "contact", "contactus",
    "mail", "post", "reception", "frontdesk", "support", "help", "hello", "hi", "team",
    "accounts", "account", "finance", "billing", "invoices", "payments", "bookings",
    "booking", "appointments", "appts", "careers", "jobs", "recruitment", "hr",
    "marketing", "newsletter", "news", "press", "media", "privacy", "dpo", "data",
    "gdpr", "complaints", "feedback", "service", "services", "customerservice",
    "customerservices", "general", "manager", "management", "partners", "property",
    "properties", "valuations", "valuation", "maintenance", "repairs", "lettingsteam",
    "salesteam", "dental", "dentist", "surgery", "practice", "practicemanager",
    "clinic", "patients", "patient", "law", "legal", "conveyancing", "probate",
    "family", "tax", "payroll", "bookkeeping", "audit", "web", "webmaster", "website",
    "it", "tech", "office1", "branch", "new", "newbusiness", "referrals", "clients",
}


def first_name_from_email(email: str) -> Optional[str]:
    """'david.mann@x.co.uk' -> 'David'. Returns None for inboxes like info@ or accounts@."""
    prefix = email.split("@", 1)[0].lower()
    compact = re.sub(r"[^a-z]", "", prefix)
    if not compact or compact in GENERIC_EMAIL_PREFIXES:
        return None
    first = re.split(r"[._\-]", prefix)[0]
    first = re.sub(r"[^a-z]", "", first)
    # Must look like a first name: letters only, 3-12 chars, not a generic word
    if 3 <= len(first) <= 12 and first not in GENERIC_EMAIL_PREFIXES and first.isalpha():
        # 'dmann' style (initial + surname) can't be trusted as a first name
        has_separator = any(sep in prefix for sep in "._-")
        if not has_separator:
            if len(first) > 8:
                return None
            # Two leading consonants that rarely start a first name = initial + surname ('dmann', 'pbywater')
            vowels = set("aeiouy")
            ok_clusters = {"br", "ch", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "kr",
                           "ph", "pr", "sc", "sh", "st", "th", "tr", "bl", "chr", "sk"}
            if first[0] not in vowels and first[1] not in vowels and first[:2] not in ok_clusters:
                return None
        return first.capitalize()
    return None


def pick_primary_email(lead: "ScrapedLead", first_name: Optional[str] = None) -> Optional[str]:
    """The best single email for the dossier: the contact's own inbox, else the main inbox."""
    if not lead.emails_found:
        return None
    if first_name:
        for em in lead.emails_found:
            if em.split("@", 1)[0].lower().startswith(first_name.lower()):
                return em
    for preferred in ("info", "enquiries", "hello", "contact", "office", "reception"):
        for em in lead.emails_found:
            if em.split("@", 1)[0].lower() == preferred:
                return em
    return lead.emails_found[0]


def infer_contact_name_and_role(
    lead: ScrapedLead, vertical_key: str
) -> Tuple[str, str]:
    """Smart contact resolver: extracts personal names from officers or email prefixes."""
    vert_cfg = VERTICAL_PRESETS.get(
        vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"]
    )

    # 1. Primary Officer match — only real people in decision-making roles
    officer = pick_decision_maker(lead.officers)
    if officer:
        first_name = first_name_from_officer(officer.name)
        if first_name:
            return first_name, officer.role

    # 2. Email Prefix Extraction (e.g. sarah@firm.co.uk or david.mann@firm.co.uk -> Sarah / David)
    for em in lead.emails_found:
        name_candidate = first_name_from_email(em)
        if name_candidate:
            return name_candidate, f"Direct Contact ({em})"

    # 3. Fallback to vertical-specific role
    return vert_cfg["fallback_greeting"], "Team / Branch Management"


def build_email_pitch(lead: ScrapedLead, vertical_key: str) -> str:
    config = VERTICAL_PRESETS.get(
        vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"]
    )
    first_name, _ = infer_contact_name_and_role(lead, vertical_key)
    crms_str = " / ".join(config["crms"][:3])

    bullets_text = "\n".join([f"- {b}" for b in config["pitch_bullets"]])

    # Personalised opening matching the reference lead style
    email_text = f"""Hi {first_name},

I hope you're well.

We work with a number of firms across the sector connecting their telephony directly into their core systems ({crms_str}) so that:

{bullets_text}

Let me know which system {lead.company_name} uses and roughly how many handsets or users you have, and I'll send over a quote.

Kind regards,
Commercial Telephony Solutions"""
    return email_text


class LeadDossierPDF(FPDF):

    def header(self):
        self.set_fill_color(30, 41, 59)  # Dark slate header bar
        self.rect(0, 0, 210, 14, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.set_xy(12, 3)
        self.cell(
            0,
            8,
            "BUSINESS CONNECTIVITY | CONFIDENTIAL LEAD RECORD",
            ln=0,
        )
        self.ln(14)

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(148, 163, 184)
        self.cell(
            0,
            6,
            "Confidential lead record - Generated for internal sales review",
            0,
            0,
            "C",
        )


def create_pdf_dossier(
    lead: ScrapedLead,
    vertical_name: str,
    pitch_text: str,
    target_crms: List[str],
) -> bytes:
    pdf = LeadDossierPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    contact_name, contact_role = infer_contact_name_and_role(
        lead, vertical_name
    )

    # 1. PRIMARY CONTACT CARD
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "PRIMARY CONTACT", ln=True)

    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, sanitize_pdf_text(contact_name), ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(71, 85, 105)
    primary_email = pick_primary_email(lead, contact_name) or "Email TBD"
    primary_phone = (
        lead.phones_found[0] if lead.phones_found else "Phone TBD"
    )
    contact_sub = f"{contact_role} - {primary_email} - {primary_phone}"
    pdf.cell(0, 5, sanitize_pdf_text(contact_sub), ln=True)

    pdf.ln(3)

    # 2. FIRM CARD
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "TARGET FIRM", ln=True)

    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, sanitize_pdf_text(lead.company_name[:55]), ln=True)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(71, 85, 105)
    addr_line = lead.registered_address or "Address not listed"
    site_line = lead.website_url or "Website not specified"
    pdf.cell(
        0,
        5,
        sanitize_pdf_text(
            f"{vertical_name} - {addr_line[:65]} - Company"
            f" #{lead.company_number or 'N/A'}"
        ),
        ln=True,
    )
    pdf.cell(0, 5, sanitize_pdf_text(f"Domain: {site_line}"), ln=True)

    if lead.site_meta_description:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(100, 116, 139)
        pdf.multi_cell(
            190, 4, sanitize_pdf_text(f'"{lead.site_meta_description[:200]}"')
        )

    pdf.ln(2)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # 3. CORE INTEGRATION HOOK
    vert_cfg = VERTICAL_PRESETS.get(
        vertical_name, VERTICAL_PRESETS["Estate & Lettings Agents"]
    )
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "SYSTEM INTEGRATION HOOK", ln=True)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(2, 132, 199)  # Highlighted blue
    crms_headline = f"{vert_cfg['primary_hook']} (confirm which)"
    pdf.cell(0, 5, sanitize_pdf_text(crms_headline), ln=True)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(51, 65, 85)
    for bullet in vert_cfg["pitch_bullets"]:
        pdf.cell(0, 4.5, sanitize_pdf_text(f"- {bullet}"), ln=True)

    pdf.ln(3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # 4. TAILORED OUTREACH EMAIL DRAFT
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(0, 4, "READY-TO-SEND OUTREACH EMAIL COPY", ln=True)

    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.set_font("Courier", "", 8)
    pdf.set_text_color(15, 23, 42)

    clean_pitch = sanitize_pdf_text(pitch_text)
    pdf.multi_cell(190, 4.2, clean_pitch, border=1, fill=True)

    output = pdf.output()
    if isinstance(output, str):
        return output.encode("latin-1", errors="replace")
    elif isinstance(output, bytearray):
        return bytes(output)
    return output


# ==========================================
# 4. STREAMLIT APPLICATION
# ==========================================

def render_leads_table(df: pd.DataFrame, key: str):
    """Selectable company table with tidy columns. Works on old and new Streamlit versions."""
    column_config = {
        "Company Name": st.column_config.TextColumn("Company Name", width="large"),
        "Company Number": st.column_config.TextColumn("Company #", width="small"),
        "Incorporated": st.column_config.DateColumn("Incorporated", format="DD MMM YYYY", width="small"),
        "Town / Postcode": st.column_config.TextColumn("Town / Postcode", width="medium"),
        "Companies House": st.column_config.LinkColumn(
            "Registry", display_text="View ↗", width="small",
            help="Opens the company's Companies House page in a new tab",
        ),
    }
    column_order = [c for c in column_config if c in df.columns]
    table_height = min(38 + 35 * len(df), 420)  # Grows with rows, scrolls after ~11
    common = dict(
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        column_config=column_config,
        column_order=column_order,
        height=table_height,
        key=key,
    )
    try:
        return st.dataframe(df, width="stretch", **common)  # Streamlit 1.46+
    except Exception:
        return st.dataframe(df, use_container_width=True, **common)  # Older Streamlit


st.set_page_config(
    page_title="Prospect Discovery & Dossier Engine", layout="wide"
)

st.title("🎯 Prospect Discovery & Dossier Generator")
st.caption(
    "Source active UK companies, enrich contact channels, and generate"
    " sector-tailored pitches and PDF briefings."
)

try:
    secret_ch_key = st.secrets.get("COMPANIES_HOUSE_KEY", "")
except Exception:
    secret_ch_key = ""

with st.sidebar:
    st.header("Settings")
    if secret_ch_key:
        # Key stays server-side: never placed in a widget, so never sent to the browser.
        ch_api_key = secret_ch_key
        st.success("Companies House API key loaded from Secrets.")
    else:
        ch_api_key = st.text_input(
            "Companies House API Key",
            type="password",
            help=(
                "Not found in Secrets. Paste a key for this session, or add"
                " COMPANIES_HOUSE_KEY to Streamlit Secrets."
            ),
        )
    if st.button("Log Out"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.divider()
    st.markdown("**Workflow:**")
    st.markdown("1. Search Active UK entities by SIC.")
    st.markdown("2. Click any table row to select.")
    st.markdown("3. Auto-find domain & scrape contact info.")
    st.markdown("4. Review sector pitch & export PDF.")

col_left, col_right = st.columns([1.05, 0.95])

with col_left:
    st.subheader("Step 1: Pick Vertical & Location")

    selected_vertical_name = st.selectbox(
        "Target Industry Vertical",
        options=list(VERTICAL_PRESETS.keys()),
        index=0,
    )
    vertical_config = VERTICAL_PRESETS[selected_vertical_name]

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        location_input = st.text_input(
            "Town, City, or County (Recommended)",
            placeholder="e.g. Manchester, Walsall, Birmingham",
        )
    with f_col2:
        keyword_filter = st.text_input(
            "Name Keyword (Optional)",
            placeholder=f"e.g. {vertical_config['search_hint']}",
        )

    r_col1, r_col2 = st.columns([1, 2])
    with r_col1:
        result_limit = st.selectbox("Results to fetch", [25, 50, 100], index=0)
    with r_col2:
        st.write("")
        st.write("")
        browse_btn = st.button("🔍 Feed Companies from Registry", type="primary")
    target_row = None

    if browse_btn:
        if not ch_api_key:
            st.error("Please supply your Companies House API key.")
        else:
            with st.spinner("Fetching active companies from registry..."):
                enricher = LeadEnricher(ch_api_key=ch_api_key)
                leads_list, search_error = enricher.browse_vertical(
                    sic_codes=vertical_config["sic_codes"],
                    location_keyword=location_input,
                    company_name_includes=keyword_filter,
                    limit=result_limit,
                )
            st.session_state["discovered_leads"] = leads_list
            st.session_state["active_vertical_name"] = selected_vertical_name
            st.session_state["selected_lead_row"] = None
            # New search = new table widget, so no stale row selection carries over.
            st.session_state["search_version"] = st.session_state.get("search_version", 0) + 1
            if search_error:
                st.error(search_error)
            elif not leads_list:
                st.warning(
                    "No active companies matched. Try a broader location"
                    " (e.g. county instead of town) or remove the name keyword."
                )

    if st.session_state.get("discovered_leads"):
        st.write("---")
        st.subheader("Step 2: Select Target Firm")
        leads_data = st.session_state["discovered_leads"]
        st.caption(
            f"{len(leads_data)} active {'company' if len(leads_data) == 1 else 'companies'} found. 👉 Tick the box at the"
            " left of a row to select it (click a column header to sort)."
        )

        df = pd.DataFrame(leads_data)
        if "Incorporated" in df.columns:
            df["Incorporated"] = pd.to_datetime(df["Incorporated"], errors="coerce")

        table_event = render_leads_table(
            df, key=f"leads_table_{st.session_state.get('search_version', 0)}"
        )

        selected_rows = table_event.selection.rows if table_event else []

        if selected_rows and selected_rows[0] < len(leads_data):
            st.session_state["selected_lead_row"] = leads_data[selected_rows[0]]
        else:
            # Nothing ticked = nothing selected. Never fall back to row 1.
            st.session_state["selected_lead_row"] = None

        target_row = st.session_state["selected_lead_row"]

    if st.session_state.get("discovered_leads") and not target_row:
        st.info("☝️ Tick a company in the table above to continue.")

    if st.session_state.get("discovered_leads") and target_row:
        st.markdown(
            f"**Selected Target:** `{target_row['Company Name']}`"
            f" *(#{target_row['Company Number']} —"
            f" {target_row['Town / Postcode']})*"
        )

        website_override = st.text_input(
            "Website URL (Optional — leave blank to auto-discover):",
            placeholder="e.g. hartnewhomes.co.uk",
        )

        enrich_btn = st.button(
            f"⚡ Auto-Discover & Enrich: {target_row['Company Name']}",
            type="secondary",
        )

        if enrich_btn:
            with st.spinner("Finding commercial website & scraping contact channels..."):
                enricher = LeadEnricher(ch_api_key=ch_api_key)
                current_vertical = st.session_state.get(
                    "active_vertical_name", "Estate & Lettings Agents"
                )
                enriched_lead = enricher.enrich_selected_company(
                    company_number=target_row["Company Number"],
                    sector_name=current_vertical,
                    manual_website=website_override,
                )
                st.session_state["current_lead"] = enriched_lead
                st.session_state.pop("custom_pitch_text", None)

with col_right:
    st.subheader("Step 3: Enriched Dossier & Pitch")

    if "current_lead" in st.session_state:
        lead: ScrapedLead = st.session_state["current_lead"]
        current_vert_name = st.session_state.get(
            "active_vertical_name", "Estate & Lettings Agents"
        )
        vert_cfg = VERTICAL_PRESETS[current_vert_name]

        tab1, tab2 = st.tabs(["📋 Lead Card & Angles", "✉️ Email Pitch & PDF"])

        with tab1:
            b1, b2, b3 = st.columns(3)
            b1.metric("Vertical", current_vert_name.split("/")[0])
            b2.metric("Company #", lead.company_number or "N/A")
            b3.metric(
                "SIC Code",
                ", ".join(lead.sic_codes) if lead.sic_codes else "Active",
            )

            st.markdown(f"### {lead.company_name}")
            st.markdown(
                f"📍 **Registered Office:** {lead.registered_address or 'Not listed'}"
            )

            if lead.website_url:
                badge = {"High": "🟢 High", "Medium": "🟡 Medium", "Low": "🟠 Low",
                         "Manual": "✍️ Entered manually"}.get(lead.website_confidence or "", "")
                st.markdown(
                    f"🌐 **Website:** [{lead.website_url}]({lead.website_url})"
                    + (f" — match confidence: **{badge}**" if badge else "")
                )
                if lead.website_reasons:
                    st.caption("Why: " + "; ".join(lead.website_reasons))
                if lead.website_confidence == "Low":
                    st.warning(
                        "This website is a weak match. Check it's the right firm before"
                        " sending, or paste the correct URL on the left and re-run."
                    )
            else:
                st.warning(
                    "🌐 Couldn't confidently find this firm's website. Paste it into"
                    " the Website URL box on the left and re-run to pull contacts."
                )
            if lead.discovery_notes:
                with st.expander("Discovery notes"):
                    for note in lead.discovery_notes:
                        st.markdown(f"- {note}")

            if lead.site_meta_description:
                st.info(f"**Site Summary:** {lead.site_meta_description}")

            st.markdown("#### Primary Contacts & Officers")
            contact_name, contact_role = infer_contact_name_and_role(
                lead, current_vert_name
            )
            st.markdown(f"**Identified Target:** `{contact_name}` ({contact_role})")

            if lead.officers:
                for off in lead.officers:
                    st.markdown(
                        f"- **{off.name}** — *{off.role}* (Appointed:"
                        f" {off.appointed_on or 'N/A'})"
                    )
            else:
                st.caption("No registered officers returned by API.")

            st.markdown("#### Discovered Channels")
            emails_display = (
                ", ".join([f"`{e}`" for e in lead.emails_found])
                if lead.emails_found
                else "*None detected*"
            )
            phones_display = (
                ", ".join([f"`{p}`" for p in lead.phones_found])
                if lead.phones_found
                else "*None detected*"
            )
            st.markdown(f"**Emails:** {emails_display}")
            st.markdown(f"**Phones:** {phones_display}")
            if lead.other_emails or lead.pages_checked:
                with st.expander("Scrape details"):
                    if lead.other_emails:
                        st.markdown(
                            "**Third-party emails ignored** (web agencies, regulators, portals): "
                            + ", ".join(f"`{e}`" for e in lead.other_emails)
                        )
                    if lead.pages_checked:
                        st.markdown("**Pages checked:**")
                        for page in lead.pages_checked:
                            st.markdown(f"- {page}")

            st.write("---")
            st.markdown(f"**Target Sector CRMs / PMS:**")
            st.markdown(f"`{'`  •  `'.join(vert_cfg['crms'])}`")
            st.markdown(f"**Core Hook Angle:** {vert_cfg['primary_hook']}")

        with tab2:
            st.markdown("#### Outreach Email Draft")
            st.caption(
                "Tweak the draft below if needed before downloading the dossier"
                " or copying to your clipboard."
            )

            if "custom_pitch_text" not in st.session_state:
                st.session_state["custom_pitch_text"] = build_email_pitch(
                    lead, current_vert_name
                )

            edited_pitch = st.text_area(
                "Email Body",
                value=st.session_state["custom_pitch_text"],
                height=250,
            )
            st.session_state["custom_pitch_text"] = edited_pitch

            pdf_bytes = create_pdf_dossier(
                lead=lead,
                vertical_name=current_vert_name,
                pitch_text=edited_pitch,
                target_crms=vert_cfg["crms"],
            )

            d_col1, d_col2 = st.columns(2)
            with d_col1:
                clean_filename = f"dossier_{re.sub(r'[^a-zA-Z0-9]', '_', lead.company_name).lower()}.pdf"
                st.download_button(
                    label="📄 Download PDF Dossier",
                    data=bytes(pdf_bytes),
                    file_name=clean_filename,
                    mime="application/pdf",
                    type="primary",
                )
            with d_col2:
                st.caption(
                    "Formatted in the standard 1-page lead sheet style."
                )

    else:
        st.info("Select a company from the feed to run automated discovery.")
