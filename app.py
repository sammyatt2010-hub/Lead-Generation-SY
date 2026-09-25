import base64
import hmac
import io
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus, urljoin, urlparse

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
# 1. VERTICALS, CRMS & PITCH PLAYBOOKS
# ==========================================

VERTICAL_PRESETS = {
    "Estate & Lettings Agents": {
        "sic_codes": ["68310"],
        "description": "Real estate agencies & letting operations",
        "search_hint": "Estate Agents",
        "crms": ["Street", "Alto", "Reapit", "Dezrez", "Jupix"],
        "primary_hook": "CRM Screen-Pop & Property File Sync",
        "pitch_bullets": [
            (
                "Screen pop-up of the client or landlord record the moment"
                " their call comes in"
            ),
            (
                "Automatic voice recording & call logging synced straight to"
                " the property file"
            ),
            "Click to dial directly from your CRM / property management portal",
            (
                "Never miss an applicant lead - missed calls instantly flagged"
                " for callback"
            ),
        ],
        "default_cta": (
            "Let me know roughly how many handsets or softphones you use"
            " across the team, and I can put together a quick, no-obligation"
            " quote."
        ),
    },
    "Dental Practices": {
        "sic_codes": ["86230"],
        "description": "Dental practice activities",
        "search_hint": "Dental Practice",
        "crms": ["Dentally", "EXACT (SOE)", "Carestream R4"],
        "primary_hook": "Patient Management System (PMS) Pop & Recall Tracking",
        "pitch_bullets": [
            (
                "Patient record pops on the reception screen the instant the"
                " phone rings"
            ),
            (
                "Calls and appointment notes log automatically against the"
                " patient chart"
            ),
            (
                "Missed inbound calls flagged immediately to protect patient"
                " booking retention"
            ),
            (
                "Call recordings stored securely and compliantly against the"
                " patient record"
            ),
        ],
        "default_cta": (
            "How many surgery handsets or reception lines does the practice"
            " run? I can share a tailored overview and cost comparison."
        ),
    },
    "Solicitors & Legal Practices": {
        "sic_codes": ["69102"],
        "description": "Solicitors & legal service providers",
        "search_hint": "Solicitors",
        "crms": ["Clio", "LEAP", "Proclaim", "Actionstep"],
        "primary_hook": "Matter-Centric Telephony & Fee-Earner Mobility",
        "pitch_bullets": [
            (
                "Dial directly out of active client or matter records in your"
                " practice management system"
            ),
            (
                "Softphone & mobile apps so fee earners take work calls securely"
                " anywhere"
            ),
            (
                "Single unified system spanning reception, remote fee earners,"
                " and all branch offices"
            ),
            (
                "Billable call duration & time tracking logged back to the"
                " client matter"
            ),
        ],
        "default_cta": (
            "Let me know which practice management system you run and your"
            " user count, and I'll send over a breakdown."
        ),
    },
    "Accountants & Auditors": {
        "sic_codes": ["69201"],
        "description": "Accounting, bookkeeping & tax consultancy",
        "search_hint": "Accountants",
        "crms": ["Iris", "CCH", "TaxCalc", "Xero Practice Manager"],
        "primary_hook": "Client Record Pop & Hybrid Advisory Telephony",
        "pitch_bullets": [
            "Client identification & contact card pop-up on inbound calls",
            "Automatic call logging against client tax and audit folders",
            (
                "Seamless call transferring between office desk phones and"
                " laptop softphones"
            ),
            (
                "Consolidated line billing to reduce standard landline rental"
                " overheads"
            ),
        ],
        "default_cta": (
            "Drop me a quick note with your team size and I'll send over a"
            " tailored specification."
        ),
    },
    "General Medical Clinics": {
        "sic_codes": ["86210"],
        "description": "General medical practice activities",
        "search_hint": "Clinic",
        "crms": ["EMIS Web", "SystmOne", "Semble", "Heydoc"],
        "primary_hook": "Clinical Triage & Patient Line Management",
        "pitch_bullets": [
            (
                "Patient record screen-pop to accelerate inbound reception"
                " triage"
            ),
            "Automated call queueing & peak-time patient callback features",
            "Compliant, encrypted voice recording stored per patient file",
            (
                "Direct transfer lines between triage staff, clinicians, and"
                " administration"
            ),
        ],
        "default_cta": (
            "Let me know how many lines you operate and I can provide an"
            " indicative setup plan."
        ),
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
                blocked = [
                    "find-and-update.company-information.service.gov.uk",
                    "companieshouse",
                    "endole",
                    "duedil",
                    "linkedin",
                    "facebook",
                    "yell.com",
                    "checkcompany",
                ]

                for link in links:
                    raw_text = link.get_text().strip()
                    domain = raw_text.split("/")[0].strip()
                    if domain and not any(b in domain.lower() for b in blocked):
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
                    em = (
                        mailto["href"]
                        .replace("mailto:", "")
                        .split("?")[0]
                        .strip()
                        .lower()
                    )
                    if em and "@" in em and "." in em:
                        if not any(
                            ext in em
                            for ext in [
                                ".png",
                                ".jpg",
                                ".webp",
                                "sentry",
                                "wixpress",
                            ]
                        ):
                            emails.add(em)

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
                            "wixpress",
                            "sentry",
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


def build_email_pitch(lead: ScrapedLead, vertical_key: str) -> str:
    config = VERTICAL_PRESETS.get(
        vertical_key, VERTICAL_PRESETS["Estate & Lettings Agents"]
    )
    recipient_name = (
        lead.officers[0].name.split()[0].title()
        if lead.officers
        else "Team"
    )
    crms_str = " / ".join(config["crms"][:3])

    bullets_text = "\n".join([f"- {b}" for b in config["pitch_bullets"]])

    email_text = f"""Hi {recipient_name},

I hope you're well.

We work with a number of firms across the sector connecting their telephony directly into their core management systems ({crms_str}) so that:

{bullets_text}

{config['default_cta']}

Kind regards,
Commercial Telephony Solutions"""
    return email_text


class LeadDossierPDF(FPDF):

    def header(self):
        self.set_fill_color(26, 32, 44)
        self.rect(0, 0, 210, 16, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(12, 4)
        self.cell(0, 8, "CONFIDENTIAL TARGET DOSSIER | COMMERCIAL BRIEFING", ln=0)
        self.ln(16)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, "Generated for internal sales review", 0, 0, "C")


def create_pdf_dossier(
    lead: ScrapedLead,
    vertical_name: str,
    pitch_text: str,
    target_crms: List[str],
) -> bytes:
    pdf = LeadDossierPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Section 1: Firm & Registration Details
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(17, 24, 39)
    pdf.cell(0, 8, sanitize_pdf_text(lead.company_name[:50]), ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(75, 85, 99)
    meta_line = f"Vertical: {vertical_name}  |  Company #{lead.company_number or 'N/A'}  |  SIC: {', '.join(lead.sic_codes) or 'Active'}"
    pdf.cell(0, 6, sanitize_pdf_text(meta_line), ln=True)

    if lead.registered_address:
        pdf.cell(
            0,
            6,
            sanitize_pdf_text(f"Registered Office: {lead.registered_address[:80]}"),
            ln=True,
        )
    if lead.website_url:
        pdf.cell(
            0,
            6,
            sanitize_pdf_text(f"Website: {lead.website_url[:80]}"),
            ln=True,
        )

    pdf.ln(4)
    pdf.set_draw_color(229, 231, 235)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Section 2: Key Contacts & Officers
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(31, 41, 55)
    pdf.cell(0, 6, "PRIMARY CONTACTS & REGISTRY OFFICERS", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(55, 65, 81)
    if lead.officers:
        for off in lead.officers[:4]:
            pdf.cell(
                0,
                5,
                sanitize_pdf_text(
                    f"- {off.name} ({off.role}) - Appointed: {off.appointed_on or 'N/A'}"
                ),
                ln=True,
            )
    else:
        pdf.cell(0, 5, "- No registered officers returned via API", ln=True)

    pdf.ln(2)
    emails_str = ", ".join(lead.emails_found) if lead.emails_found else "None"
    phones_str = ", ".join(lead.phones_found) if lead.phones_found else "None"
    pdf.cell(0, 5, sanitize_pdf_text(f"Discovered Email(s): {emails_str}"), ln=True)
    pdf.cell(0, 5, sanitize_pdf_text(f"Discovered Phone(s): {phones_str}"), ln=True)

    pdf.ln(4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Section 3: Sector CRM Target & Angles
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "SECTOR INTEGRATION HOOK", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        0,
        5,
        sanitize_pdf_text(f"Typical Sector CRMs/PMS: {', '.join(target_crms)}"),
        ln=True,
    )
    pdf.ln(4)

    # Section 4: Tailored Outreach Pitch Draft
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, "TAILORED OUTREACH EMAIL DRAFT", ln=True)

    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(203, 213, 225)
    pdf.set_font("Courier", "", 8.5)
    pdf.set_text_color(15, 23, 42)

    clean_pitch = sanitize_pdf_text(pitch_text)
    pdf.multi_cell(190, 4.5, clean_pitch, border=1, fill=True)

    # Universal bytes extraction across fpdf / fpdf2
    output = pdf.output()
    if isinstance(output, str):
        return output.encode("latin-1", errors="replace")
    elif isinstance(output, bytearray):
        return bytes(output)
    return output


# ==========================================
# 4. STREAMLIT APPLICATION
# ==========================================

st.set_page_config(
    page_title="Prospect Discovery & Dossier Engine", layout="wide"
)

st.title("🎯 Prospect Discovery & Dossier Generator")
st.caption(
    "Source active UK companies, enrich contact channels, and generate"
    " sector-tailored pitches and PDF briefings."
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
                st.session_state["selected_lead_row"] = None

    if st.session_state.get("discovered_leads"):
        st.write("---")
        st.subheader("Step 2: Select Target Firm")
        st.caption(
            "👉 Click anywhere on a company row below to select it for"
            " enrichment."
        )

        leads_data = st.session_state["discovered_leads"]
        df = pd.DataFrame(leads_data)

        table_event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
        )

        selected_rows = table_event.selection.rows if table_event else []

        if selected_rows:
            st.session_state["selected_lead_row"] = leads_data[selected_rows[0]]
        elif (
            "selected_lead_row" not in st.session_state
            or not st.session_state["selected_lead_row"]
        ):
            st.session_state["selected_lead_row"] = leads_data[0]

        target_row = st.session_state["selected_lead_row"]

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
                st.markdown(f"🌐 **Website:** [{lead.website_url}]({lead.website_url})")

            if lead.site_meta_description:
                st.info(f"**Site Summary:** {lead.site_meta_description}")

            st.markdown("#### Primary Decision Makers (Active Officers)")
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
                height=260,
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
                    "Ready to copy and paste for manual review or dispatch."
                )

    else:
        st.info("Select a company from the feed to run automated discovery.")
