import base64
import hmac
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

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
        "search_hint": "Property, Lettings, Estates",
    },
    "Dental Practices": {
        "sic_codes": ["86230"],
        "description": "Dental practice activities",
        "search_hint": "Dental, Teeth, Orthodontic",
    },
    "Solicitors & Legal Practices": {
        "sic_codes": ["69102"],
        "description": "Solicitors & legal service providers",
        "search_hint": "Solicitors, Law, Legal",
    },
    "Accountants & Auditors": {
        "sic_codes": ["69201"],
        "description": "Accounting, bookkeeping, auditing & tax consultancy",
        "search_hint": "Accountants, Accountancy, Tax",
    },
    "General Medical Clinics": {
        "sic_codes": ["86210"],
        "description": "General medical practice activities",
        "search_hint": "Clinic, Medical, Health",
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
        limit: int = 15,
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

        # Fallback to standard search if advanced search has zero results with location
        if location_keyword:
            return self.search_company_by_keyword(
                f"{company_name_includes or ''} {location_keyword}", limit=limit
            )

        return []

    def search_company_by_keyword(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Standard search fallback."""
        if not self.ch_api_key or not query.strip():
            return []
        url = f"{self.base_url}/search/companies"
        try:
            resp = requests.get(
                url,
                headers=self.headers,
                params={"q": query, "items_per_page": limit},
                timeout=10,
            )
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                return [
                    {
                        "Company Name": i.get("title", ""),
                        "Company Number": i.get("company_number", ""),
                        "Incorporated": i.get("date_of_creation", "N/A"),
                        "Town / Postcode": i.get("address_snippet", ""),
                        "Status": i.get("company_status", "").title(),
                    }
                    for i in items
                ]
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

    def scrape_website(self, url: str) -> Dict[str, Any]:
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

                meta_tag = soup.find("meta", attrs={"name": "description"})
                if meta_tag and meta_tag.get("content"):
                    results["description"] = meta_tag["content"].strip()

                for mailto in soup.select('a[href^="mailto:"]'):
                    email = mailto["href"].replace("mailto:", "").split("?")[0]
                    if email and "@" in email:
                        results["emails"].add(email.strip().lower())

                for tel in soup.select('a[href^="tel:"]'):
                    phone = tel["href"].replace("tel:", "").strip()
                    if len(phone) >= 9:
                        results["phones"].add(phone)

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

    def enrich_selected_company(
        self,
        company_number: str,
        sector_name: str,
        website: Optional[str] = None,
    ) -> ScrapedLead:
        ch_data = self.get_company_details(company_number)

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

        officers = self.get_officers(company_number)
        site_contacts = (
            self.scrape_website(website)
            if website
            else {"emails": [], "phones": [], "description": ""}
        )

        return ScrapedLead(
            company_name=ch_data.get("company_name", company_number),
            company_number=company_number,
            sic_codes=ch_data.get("sic_codes", []),
            sector_guess=sector_name,
            registered_address=registered_address,
            website_url=website,
            phones_found=site_contacts["phones"],
            emails_found=site_contacts["emails"],
            officers=officers,
            site_meta_description=site_contacts["description"],
        )


# ==========================================
# 3. STREAMLIT APPLICATION (FEED FLOW)
# ==========================================

st.set_page_config(page_title="Prospect Discovery Engine", layout="wide")

st.title("🎯 Prospect Feed & Enrichment Engine")
st.caption(
    "Browse live UK companies by industry vertical and location, then enrich on"
    " demand."
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
    st.markdown("**How this works:**")
    st.markdown("1. Choose vertical & target town.")
    st.markdown("2. Review company list from registry.")
    st.markdown("3. Select one & enrich into dossier.")

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
            "Town, City, or County (Optional)",
            placeholder="e.g. Manchester, Chester, Shrewsbury",
        )
    with f_col2:
        keyword_filter = st.text_input(
            "Name Keyword (Optional)",
            placeholder=f"e.g. {vertical_config['search_hint'].split(',')[0]}",
        )

    browse_btn = st.button("🔍 Feed Companies from Registry", type="primary")

    if browse_btn:
        if not ch_api_key:
            st.error(
                "Please ensure your Companies House API key is provided in the"
                " sidebar or secrets."
            )
        else:
            with st.spinner("Querying active registry entities..."):
                enricher = LeadEnricher(ch_api_key=ch_api_key)
                leads_list = enricher.browse_vertical(
                    sic_codes=vertical_config["sic_codes"],
                    location_keyword=location_input,
                    company_name_includes=keyword_filter,
                    limit=20,
                )
                st.session_state["discovered_leads"] = leads_list
                st.session_state["active_vertical_name"] = selected_vertical_name

    # Step 2: Show Discovered Companies
    if st.session_state.get("discovered_leads"):
        st.write("---")
        st.subheader("Step 2: Select a Target to Enrich")

        leads_data = st.session_state["discovered_leads"]
        df = pd.DataFrame(leads_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Selection Dropdown
        company_options = {
            f"{row['Company Name']} ({row['Company Number']}) — {row['Town / Postcode']}": row[
                "Company Number"
            ]
            for row in leads_data
        }

        selected_label = st.selectbox(
            "Choose Company to Generate Dossier:",
            options=list(company_options.keys()),
        )
        selected_company_number = company_options[selected_label]

        website_enrich_input = st.text_input(
            "Company Website (Optional - for scraping phone/email/description):",
            placeholder="e.g. companyname.co.uk",
        )

        enrich_btn = st.button("⚡ Enrich Target Profile", type="secondary")

        if enrich_btn:
            with st.spinner("Extracting officers, filing history, and web data..."):
                enricher = LeadEnricher(ch_api_key=ch_api_key)
                current_vertical = st.session_state.get(
                    "active_vertical_name", "General B2B"
                )
                enriched_lead = enricher.enrich_selected_company(
                    company_number=selected_company_number,
                    sector_name=current_vertical,
                    website=website_enrich_input,
                )
                st.session_state["current_lead"] = enriched_lead

with col_right:
    st.subheader("Step 3: Enriched Lead Dossier")

    if "current_lead" in st.session_state:
        lead: ScrapedLead = st.session_state["current_lead"]

        # Metric Badges
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
            st.markdown(f"🌐 **Website:** [{lead.website_url}](https://{lead.website_url})")

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
        st.markdown(
            "**Emails:** " + (", ".join(lead.emails_found) or "None detected")
        )
        st.markdown(
            "**Phone Numbers:** "
            + (", ".join(lead.phones_found) or "None detected")
        )

        st.success(
            "Target ready. Next step: Generate tailored industry pitch &"
            " email copy."
        )
    else:
        st.info("Pick a vertical and company on the left to see the enriched dossier here.")
