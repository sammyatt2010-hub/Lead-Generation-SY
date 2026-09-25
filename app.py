import base64
import hmac
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup
import pandas as pd
from pydantic import BaseModel, Field
import requests
import streamlit as st

# ==========================================
# 0. PASSWORD GATEWAY (STREAMLIT SECRETS)
# ==========================================


def check_password() -> bool:
    """Returns True if user is authenticated via APP_PASSWORD in secrets."""
    if "APP_PASSWORD" not in st.secrets:
        return True

    def login_form():
        with st.form("Credentials"):
            st.text_input(
                "Enter Access Password", type="password", key="password"
            )
            st.form_submit_button("Log In", on_click=password_entered)

    def password_entered():
        if hmac.compare_digest(
            st.session_state["password"], st.secrets["APP_PASSWORD"]
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
# 1. VERTICALS & DATA MODELS
# ==========================================

VERTICAL_PRESETS = {
    "Estate & Lettings Agents": {
        "sic_codes": ["68310"],
        "description": "Real estate agencies & letting operations",
        "search_hint": "Estate Agents",
    },
    "Dental Practices": {
        "sic_codes": ["86230"],
        "description": "Dental practice activities",
        "search_hint": "Dental Practice",
    },
    "Solicitors & Legal Practices": {
        "sic_codes": ["69102"],
        "description": "Solicitors & legal service providers",
        "search_hint": "Solicitors",
    },
    "Accountants & Auditors": {
        "sic_codes": ["69201"],
        "description": "Accounting, bookkeeping & tax consultancy",
        "search_hint": "Accountants",
    },
    "General Medical Clinics": {
        "sic_codes": ["86210"],
        "description": "General medical practice activities",
        "search_hint": "Clinic",
    },
}


class OfficerInfo(BaseModel):
    name: str
    role: str
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


# ==========================================
# 2. ENRICHMENT & SCRAPING ENGINE
# ==========================================


class LeadEnricher:

    def __init__(self, ch_api_key: Optional[str] = None):
        self.ch_api_key = ch_api_key.strip() if ch_api_key else None
        self.base_url = "https://api.company-information.service.gov.uk"
        self.headers = self._get_auth_headers()
        self.web_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

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
    ) -> List[Dict[str, Any]]:
        """Feed active companies by SIC code vertical and location."""
        if not self.ch_api_key:
            return []

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
                        }
                    )
                return results
        except Exception:
            pass

        return []

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
                        officers.append(
                            OfficerInfo(
                                name=item.get("name", "Unknown"),
                                role=item.get(
                                    "officer_role", "Director"
                                ).title(),
                                appointed_on=item.get("appointed_on"),
                            )
                        )
        except Exception:
            pass
        return officers

    def auto_discover_website(
        self, company_name: str, location: Optional[str] = None
    ) -> Optional[str]:
        """Automatically find the company's official domain via web query."""
        clean_name = re.sub(
            r"\b(LTD|LIMITED|PLC|LLP|GROUP|UK)\b",
            "",
            company_name,
            flags=re.IGNORECASE,
        ).strip()
        query = f"{clean_name} {location or ''} official website UK"

        search_url = (
            f"https://html.duckduckgo.com/html/?q={quote_plus(query.strip())}"
        )
        try:
            resp = requests.get(
                search_url, headers=self.web_headers, timeout=6
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                links = soup.select(".result__url")
                blocked_domains = [
                    "find-and-update.company-information.service.gov.uk",
                    "companieshouse",
                    "endole.co.uk",
                    "duedil.com",
                    "linkedin.com",
                    "facebook.com",
                    "yell.com",
                    "checkcompany.co.uk",
                    "thephonebook.bt.com",
                    "192.com",
                ]

                for link in links:
                    raw_text = link.get_text().strip()
                    domain = raw_text.split("/")[0].strip()
                    if domain and not any(b in domain for b in blocked_domains):
                        return f"https://{domain}"
        except Exception:
            pass
        return None

    def scrape_contact_channels(self, base_url: str) -> Dict[str, Any]:
        emails: Set[str] = set()
        phones: Set[str] = set()
        description = ""

        if not base_url:
            return {
                "emails": [],
                "phones": [],
                "description": "",
                "resolved_url": None,
            }

        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"

        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"

        pages_to_check = [
            root,
            urljoin(root, "/contact"),
            urljoin(root, "/contact-us"),
            urljoin(root, "/about"),
        ]

        for url in pages_to_check:
            try:
                resp = requests.get(url, headers=self.web_headers, timeout=6)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                if not description:
                    meta_tag = soup.find("meta", attrs={"name": "description"})
                    if meta_tag and meta_tag.get("content"):
                        description = meta_tag["content"].strip()

                for mailto in soup.select('a[href^="mailto:"]'):
                    em = mailto["href"].replace("mailto:", "").split("?")[0]
                    em_clean = em.strip().lower()
                    if em_clean and "@" in em_clean and "." in em_clean:
                        if not any(
                            ext in em_clean
                            for ext in [".png", ".jpg", "sentry.io"]
                        ):
                            emails.add(em_clean)

                for tel in soup.select('a[href^="tel:"]'):
                    ph = tel["href"].replace("tel:", "").strip()
                    if len(ph) >= 9:
                        phones.add(ph)

                page_text = soup.get_text()

                text_emails = re.findall(
                    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
                    page_text,
                )
                for te in text_emails:
                    te_clean = te.strip().lower()
                    if not any(
                        ext in te_clean
                        for ext in [
                            ".png",
                            ".jpg",
                            ".webp",
                            "wixpress.com",
                            "sentry.io",
                        ]
                    ):
                        emails.add(te_clean)

                uk_phones = re.findall(
                    r"(?:(?:\+44\s?\(0\)\s?|\+44\s?|0)[1-9]\d{2,4}\s?\d{3,4}\s?\d{3,4})",
                    page_text,
                )
                for p in uk_phones[:4]:
                    cleaned = p.strip()
                    if len(cleaned) >= 10:
                        phones.add(cleaned)

            except Exception:
                continue

        return {
            "emails": sorted(list(emails)),
            "phones": sorted(list(phones)),
            "description": description,
            "resolved_url": root,
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
        town_or_postcode = address_dict.get("locality") or address_dict.get(
            "postal_code"
        )

        officers = self.get_officers(company_number)

        target_website = manual_website.strip() if manual_website else None
        if not target_website:
            target_website = self.auto_discover_website(
                company_name, location=town_or_postcode
            )

        site_contacts = (
            self.scrape_contact_channels(target_website)
            if target_website
            else {
                "emails": [],
                "phones": [],
                "description": "",
                "resolved_url": None,
            }
        )

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
        )


# ==========================================
# 3. STREAMLIT APPLICATION
# ==========================================

st.set_page_config(page_title="Prospect Discovery Engine", layout="wide")

st.title("🎯 Prospect Feed & Automated Web Discovery")
st.caption(
    "Query the Companies House registry, then click any row in the table to"
    " enrich contacts."
)

default_ch_key = st.secrets.get("COMPANIES_HOUSE_KEY", "")

with st.sidebar:
    st.header("Settings")
    ch_api_key = st.text_input(
        "Companies House API Key",
        value=default_ch_key,
        type="password",
        help="developer.company-information.service.gov.uk",
    )
    if st.button("Log Out"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.divider()
    st.markdown("**Automated Pipeline:**")
    st.markdown("1. Search Active UK entities by SIC.")
    st.markdown("2. Click any table row to select.")
    st.markdown("3. Auto-find domain & scrape direct contact points.")

col_left, col_right = st.columns([1.1, 0.9])

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
            placeholder="e.g. Manchester, Chester, Birmingham",
        )
    with f_col2:
        keyword_filter = st.text_input(
            "Name Keyword (Optional)",
            placeholder=f"e.g. {vertical_config['search_hint']}",
        )

    browse_btn = st.button("🔍 Feed Companies from Registry", type="primary")

    if browse_btn:
        if not ch_api_key:
            st.error("Please supply your Companies House API key.")
        else:
            with st.spinner("Fetching active companies from registry..."):
                enricher = LeadEnricher(ch_api_key=ch_api_key)
                leads_list = enricher.browse_vertical(
                    sic_codes=vertical_config["sic_codes"],
                    location_keyword=location_input,
                    company_name_includes=keyword_filter,
                    limit=25,
                )
                st.session_state["discovered_leads"] = leads_list
                st.session_state["active_vertical_name"] = selected_vertical_name
                # Reset any previous row selection
                st.session_state["selected_lead_row"] = None

    # Step 2: Select & Auto-Enrich via Direct Table Click
    if st.session_state.get("discovered_leads"):
        st.write("---")
        st.subheader("Step 2: Click a Row to Select Target")
        st.caption(
            "👉 Click anywhere on a company row below to select it for"
            " enrichment."
        )

        leads_data = st.session_state["discovered_leads"]
        df = pd.DataFrame(leads_data)

        # Native interactive row selection table
        table_event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
        )

        # Check if user clicked a row in the table
        selected_rows = table_event.selection.rows if table_event else []

        if selected_rows:
            st.session_state["selected_lead_row"] = leads_data[selected_rows[0]]
        elif (
            "selected_lead_row" not in st.session_state
            or not st.session_state["selected_lead_row"]
        ):
            # Default to the first row if nothing selected yet
            st.session_state["selected_lead_row"] = leads_data[0]

        target_row = st.session_state["selected_lead_row"]

        st.markdown(
            f"**Selected Target:** `{target_row['Company Name']}`"
            f" *(#{target_row['Company Number']} —"
            f" {target_row['Town / Postcode']})*"
        )

        website_override = st.text_input(
            "Website URL (Optional — leave blank to auto-discover):",
            placeholder="e.g. example.co.uk",
        )

        enrich_btn = st.button(
            f"⚡ Auto-Discover & Enrich: {target_row['Company Name']}",
            type="secondary",
        )

        if enrich_btn:
            with st.spinner("Finding commercial website & scraping contact channels..."):
                enricher = LeadEnricher(ch_api_key=ch_api_key)
                current_vertical = st.session_state.get(
                    "active_vertical_name", "General B2B"
                )
                enriched_lead = enricher.enrich_selected_company(
                    company_number=target_row["Company Number"],
                    sector_name=current_vertical,
                    manual_website=website_override,
                )
                st.session_state["current_lead"] = enriched_lead

with col_right:
    st.subheader("Step 3: Enriched Lead Dossier")

    if "current_lead" in st.session_state:
        lead: ScrapedLead = st.session_state["current_lead"]

        b1, b2, b3 = st.columns(3)
        b1.metric("Vertical", lead.sector_guess.split("/")[0])
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
            st.markdown(f"🌐 **Discovered Website:** [{lead.website_url}]({lead.website_url})")
        else:
            st.warning("⚠️ Commercial website could not be automatically resolved. You can paste it in the override box on the left.")

        if lead.site_meta_description:
            st.info(f"**Site Summary:** {lead.site_meta_description}")

        st.write("---")
        st.markdown("#### Primary Decision Makers (Active Officers)")
        if lead.officers:
            for off in lead.officers:
                st.markdown(
                    f"- **{off.name}** — *{off.role}* (Appointed:"
                    f" {off.appointed_on or 'N/A'})"
                )
        else:
            st.caption("No registered officers returned by API.")

        st.write("---")
        st.markdown("#### Scraped Contact Channels")

        if lead.emails_found:
            st.markdown("**Discovered Inboxes:**")
            for em in lead.emails_found:
                st.markdown(f"- ✉️ `{em}`")
        else:
            st.markdown("**Emails:** *None found on crawled pages*")

        if lead.phones_found:
            st.markdown("**Discovered Telephones:**")
            for ph in lead.phones_found:
                st.markdown(f"- 📞 `{ph}`")
        else:
            st.markdown("**Phones:** *None found on crawled pages*")

        st.write("---")
        st.success(
            "Profile ready. Next: Connect LLM Pitch & Dossier PDF Builder."
        )
    else:
        st.info("Click any company row in the table to enrich its profile.")
