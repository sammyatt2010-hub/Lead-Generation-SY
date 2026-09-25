import base64
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import requests
import streamlit as st

# ==========================================
# 1. DATA MODELS & SECTOR CONFIGURATION
# ==========================================

SIC_SECTORS: Dict[str, str] = {
    "68310": "Real Estate / Property",
    "68209": "Real Estate / Letting",
    "86230": "Dental Practice",
    "86210": "General Medical Practice",
    "69102": "Solicitors & Legal Services",
    "69101": "Barristers",
    "69201": "Accounting & Auditing",
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

    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.ch_api_key:
            return {}
        # Companies House requires HTTP Basic Auth with API key as username and empty password
        token = base64.b64encode(f"{self.ch_api_key}:".encode("utf-8")).decode(
            "utf-8"
        )
        return {"Authorization": f"Basic {token}"}

    def search_company(self, query: str) -> List[Dict[str, Any]]:
        """Search Companies House by company name or number."""
        if not self.ch_api_key:
            return []
        url = f"{self.base_url}/search/companies"
        try:
            resp = requests.get(
                url,
                headers=self.headers,
                params={"q": query, "items_per_page": 5},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("items", [])
        except Exception:
            pass
        return []

    def get_company_details(self, company_number: str) -> Dict[str, Any]:
        """Fetch primary company profile."""
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
        """Fetch active officers and directors."""
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
                    # Filter out resigned directors
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

    def scrape_website(self, url: str) -> Dict[str, Any]:
        """Scrape contact info and meta description from target website."""
        results = {"emails": set(), "phones": set(), "description": ""}
        if not url:
            return results

        clean_url = url.strip()
        if not clean_url.startswith("http"):
            clean_url = f"https://{clean_url}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

        try:
            resp = requests.get(clean_url, headers=headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Meta description
                meta_tag = soup.find("meta", attrs={"name": "description"})
                if meta_tag and meta_tag.get("content"):
                    results["description"] = meta_tag["content"].strip()

                # mailto links
                for mailto in soup.select('a[href^="mailto:"]'):
                    email = mailto["href"].replace("mailto:", "").split("?")[0]
                    if email and "@" in email:
                        results["emails"].add(email.strip().lower())

                # tel links
                for tel in soup.select('a[href^="tel:"]'):
                    phone = tel["href"].replace("tel:", "").strip()
                    if len(phone) >= 9:
                        results["phones"].add(phone)

                # Regex UK phone backup
                raw_text = soup.get_text()
                uk_phones = re.findall(
                    r"(?:(?:\+44\s?\(0\)\s?|\+44\s?|0)[1-9]\d{2,4}\s?\d{3,4}\s?\d{3,4})",
                    raw_text,
                )
                for p in uk_phones[:3]:
                    cleaned = p.strip()
                    if len(cleaned) >= 10:
                        results["phones"].add(cleaned)
        except Exception:
            pass

        return {
            "emails": list(results["emails"]),
            "phones": list(results["phones"]),
            "description": results["description"],
        }

    def build_lead_profile(
        self, company_identifier: str, website: Optional[str] = None
    ) -> ScrapedLead:
        """Query Companies House and enrich with web scrape data."""
        items = self.search_company(company_identifier)
        ch_data = {}
        company_num = None

        if items:
            top_hit = items[0]
            company_num = top_hit.get("company_number")
            ch_data = self.get_company_details(company_num)

        # Build address
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

        # Detect sector from SIC code
        sic_codes = ch_data.get("sic_codes", [])
        sector_guess = "General B2B"
        for code in sic_codes:
            if code in SIC_SECTORS:
                sector_guess = SIC_SECTORS[code]
                break

        # Officers & web contacts
        officers = self.get_officers(company_num) if company_num else []
        site_contacts = (
            self.scrape_website(website)
            if website
            else {"emails": [], "phones": [], "description": ""}
        )

        return ScrapedLead(
            company_name=ch_data.get("company_name", company_identifier),
            company_number=company_num,
            sic_codes=sic_codes,
            sector_guess=sector_guess,
            registered_address=registered_address,
            website_url=website,
            phones_found=site_contacts["phones"],
            emails_found=site_contacts["emails"],
            officers=officers,
            site_meta_description=site_contacts["description"],
        )


# ==========================================
# 3. STREAMLIT FRONTEND
# ==========================================

st.set_page_config(page_title="Lead Dossier Ingestion", layout="wide")

st.title("🎯 Prospect Ingestion Engine")
st.caption(
    "Query Companies House registry and scrape primary web contacts into a"
    " prospect dossier."
)

with st.sidebar:
    st.header("Settings")
    ch_api_key = st.text_input(
        "Companies House API Key",
        type="password",
        help="Free key from developer.company-information.service.gov.uk",
    )
    st.divider()
    st.markdown("**Supported Verticals**")
    st.markdown("- Estate & Lettings (SIC 68310)")
    st.markdown("- Dental & Healthcare (SIC 86230)")
    st.markdown("- Legal & Solicitors (SIC 69102)")
    st.markdown("- General Commercial B2B")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Target Business")
    company_query = st.text_input(
        "Company Name or Reg Number",
        placeholder="e.g. Monopoly Buy Sell Rent",
    )
    website_input = st.text_input(
        "Company Website (Optional for contact scraping)",
        placeholder="e.g. monopolybuysellrent.co.uk",
    )
    fetch_btn = st.button("Fetch & Enrich Prospect", type="primary")

if fetch_btn and company_query:
    with st.spinner("Querying Companies House & scraping website..."):
        enricher = LeadEnricher(ch_api_key=ch_api_key)
        lead = enricher.build_lead_profile(
            company_query, website=website_input
        )
        st.session_state["current_lead"] = lead

if "current_lead" in st.session_state:
    lead = st.session_state["current_lead"]

    with col2:
        st.subheader("2. Ingested Target Profile")

        # Metrics overview
        badge_cols = st.columns(3)
        badge_cols[0].metric("Detected Vertical", lead.sector_guess)
        badge_cols[1].metric("Company Number", lead.company_number or "N/A")
        badge_cols[2].metric(
            "SIC Code",
            ", ".join(lead.sic_codes) if lead.sic_codes else "Unknown",
        )

        st.markdown(f"**Official Name:** {lead.company_name}")
        st.markdown(
            f"**Registered Address:** {lead.registered_address or 'Not found'}"
        )

        if lead.site_meta_description:
            st.info(f"**Website Summary:** {lead.site_meta_description}")

        st.write("---")
        st.markdown("#### Primary Contacts & Officers")

        c_col1, c_col2 = st.columns(2)
        with c_col1:
            st.markdown("**Active Registry Officers:**")
            if lead.officers:
                for off in lead.officers:
                    st.markdown(
                        f"- **{off.name}** ({off.role})  \n  *Appointed:"
                        f" {off.appointed_on or 'N/A'}*"
                    )
            else:
                st.write("No active officers found via API.")

        with c_col2:
            st.markdown("**Scraped Contact Points:**")
            st.markdown(
                "**Emails:** "
                + (", ".join(lead.emails_found) or "None detected")
            )
            st.markdown(
                "**Phone Numbers:** "
                + (", ".join(lead.phones_found) or "None detected")
            )

        st.success(
            "Data ingestion complete. Ready to pass this payload into the LLM"
            " Hook Engine."
        )
