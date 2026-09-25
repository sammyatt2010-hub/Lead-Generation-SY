import base64
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
import requests

# SIC code mappings to our business playbooks
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


class LeadEnricher:

    def __init__(self, ch_api_key: Optional[str] = None):
        self.ch_api_key = ch_api_key
        self.base_url = "https://api.company-information.service.gov.uk"
        self.headers = self._get_auth_headers()

    def _get_auth_headers(self) -> Dict[str, str]:
        if not self.ch_api_key:
            return {}
        # Companies House requires HTTP Basic Auth with API key as username and blank password
        token = base64.b64encode(f"{self.ch_api_key}:".encode("utf-8")).decode(
            "utf-8"
        )
        return {"Authorization": f"Basic {token}"}

    def search_company(self, query: str) -> List[Dict[str, Any]]:
        """Search Companies House by company name or number."""
        if not self.ch_api_key:
            return []
        url = f"{self.base_url}/search/companies"
        resp = requests.get(
            url,
            headers=self.headers,
            params={"q": query, "items_per_page": 5},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("items", [])
        return []

    def get_company_details(self, company_number: str) -> Dict[str, Any]:
        """Fetch primary company profile."""
        if not self.ch_api_key:
            return {}
        url = f"{self.base_url}/company/{company_number}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        return resp.json() if resp.status_code == 200 else {}

    def get_officers(self, company_number: str) -> List[OfficerInfo]:
        """Fetch active officers/directors."""
        if not self.ch_api_key:
            return []
        url = f"{self.base_url}/company/{company_number}/officers"
        resp = requests.get(
            url,
            headers=self.headers,
            params={"register_view": "true"},
            timeout=10,
        )
        officers = []
        if resp.status_code == 200:
            for item in resp.json().get("items", []):
                # Filter out resigned directors
                if not item.get("resigned_on"):
                    officers.append(
                        OfficerInfo(
                            name=item.get("name", "Unknown"),
                            role=item.get("officer_role", "Director").title(),
                            appointed_on=item.get("appointed_on"),
                        )
                    )
        return officers

    def scrape_website(self, url: str) -> Dict[str, Any]:
        """Scrape primary contact details and meta description from the company website."""
        results = {
            "emails": set(),
            "phones": set(),
            "description": "",
        }
        if not url:
            return results

        if not url.startswith("http"):
            url = f"https://{url}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }

        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code != 200:
                return results

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract meta description
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                results["description"] = meta_tag["content"].strip()

            # Find all mailto: links
            for mailto in soup.select('a[href^="mailto:"]'):
                email = mailto["href"].replace("mailto:", "").split("?")[0]
                if email and "@" in email:
                    results["emails"].add(email.strip().lower())

            # Find tel: links
            for tel in soup.select('a[href^="tel:"]'):
                phone = tel["href"].replace("tel:", "").strip()
                if len(phone) >= 9:
                    results["phones"].add(phone)

            # Regex backup across HTML content for standard UK telephone formats
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
            pass  # Fallback gracefully if site is blocked or offline

        return {
            "emails": list(results["emails"]),
            "phones": list(results["phones"]),
            "description": results["description"],
        }

    def build_lead_profile(
        self, company_identifier: str, website: Optional[str] = None
    ) -> ScrapedLead:
        """Master method: Resolves company metadata, directors, and web contacts."""
        # 1. Look up Companies House record
        items = self.search_company(company_identifier)
        ch_data = {}
        company_num = None

        if items:
            top_hit = items[0]
            company_num = top_hit.get("company_number")
            ch_data = self.get_company_details(company_num)

        # 2. Extract address and SIC codes
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

        sic_codes = ch_data.get("sic_codes", [])
        sector_guess = "General B2B"
        for code in sic_codes:
            if code in SIC_SECTORS:
                sector_guess = SIC_SECTORS[code]
                break

        # 3. Pull active directors
        officers = self.get_officers(company_num) if company_num else []

        # 4. Scrape website if provided
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
