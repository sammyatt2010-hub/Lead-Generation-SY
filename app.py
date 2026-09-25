import streamlit as st
from modules.scraper import LeadEnricher

st.set_page_config(page_title="Lead Dossier Ingestion", layout="wide")

st.title("🎯 Prospect Ingestion Engine")
st.caption(
    "Query Companies House registry and scrape primary web contacts to assemble lead dossiers."
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
    st.subheader("1. Identify Target")
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
    with st.spinner("Querying registry & parsing website..."):
        enricher = LeadEnricher(ch_api_key=ch_api_key)
        lead = enricher.build_lead_profile(
            company_query, website=website_input
        )
        st.session_state["current_lead"] = lead

if "current_lead" in st.session_state:
    lead = st.session_state["current_lead"]

    with col2:
        st.subheader("2. Ingested Dossier Metadata")

        # Top-level tags
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

        # Contacts discovered
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
                st.write("No officers found via API.")

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
            "Data ingestion complete. Ready to pass this payload into the LLM Hook Engine."
        )
