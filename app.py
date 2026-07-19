import streamlit as st
from pypdf import PdfReader
import pandas as pd
import re
import io

def extract_info_from_text(text):
    data = {
        "Property No": None,
        "Start Date": None,
        "End Date": None,
        "Actual Contract Amount": None,
        "Tenant Name": None,
        "Emirates ID": None,
        "DEWA Premise No": None
    }

    # Regex patterns optimized for EJARI contracts
    prop_no_match = re.search(r'Property No[^\d]*(\d+)', text, re.IGNORECASE)
    start_date_match = re.search(r'Start Date[^\d]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
    end_date_match = re.search(r'End Date[^\d]*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
    amount_match = re.search(r'Actual Contract Amount[^\d]*([\d,.]+\s*AED)', text, re.IGNORECASE)
    tenant_match = re.search(r'Tenant Name\s+([A-Za-z\s]+)', text, re.IGNORECASE)
    eid_match = re.search(r'Emirates ID[^\d]*(\d{15})', text, re.IGNORECASE)
    dewa_match = re.search(r'(?:DEWA Premise No.*?|رقم ديوا)[^\d]*(\d{9,})', text, re.IGNORECASE)

    # Fallbacks
    if not amount_match:
        amount_match = re.search(r'Contract Value AED\s*([\d,.]+)', text, re.IGNORECASE)

    if prop_no_match: data["Property No"] = prop_no_match.group(1).strip()
    if start_date_match: data["Start Date"] = start_date_match.group(1).strip()
    if end_date_match: data["End Date"] = end_date_match.group(1).strip()
    if amount_match: data["Actual Contract Amount"] = amount_match.group(1).strip()
    if tenant_match: data["Tenant Name"] = tenant_match.group(1).strip()
    if eid_match: data["Emirates ID"] = eid_match.group(1).strip()
    if dewa_match: data["DEWA Premise No"] = dewa_match.group(1).strip()

    return data

def process_pdf(file_bytes):
    full_text = ""
    # Use pypdf which is much lighter on memory
    reader = PdfReader(io.BytesIO(file_bytes))
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            full_text += extracted + "\n"
            
    return extract_info_from_text(full_text)

# --- Streamlit UI ---
st.set_page_config(page_title="Tenancy Contract Extractor", layout="wide")
st.title("📄 Tenancy Contract Data Extractor")

# Initialize session state 
if 'extracted_data' not in st.session_state:
    st.session_state.extracted_data = None

# Using st.form prevents premature reruns while interacting with the uploader
with st.form("extractor_form"):
    uploaded_files = st.file_uploader("Upload PDF Contracts", type="pdf", accept_multiple_files=True)
    submit_button = st.form_submit_button("Extract Information", type="primary")

if submit_button and uploaded_files:
    results = []
    
    with st.spinner(f'Processing {len(uploaded_files)} files...'):
        for file in uploaded_files:
            try:
                file_bytes = file.getvalue()
                info = process_pdf(file_bytes)
                info["Filename"] = file.name
                results.append(info)
            except Exception as e:
                st.error(f"Error reading {file.name}: {e}")
    
    if results:
        df = pd.DataFrame(results)
        cols = ["Filename", "Property No", "Start Date", "End Date", "Actual Contract Amount", "Tenant Name", "Emirates ID", "DEWA Premise No"]
        
        # Save dataframe to session state
        st.session_state.extracted_data = df[cols]

# Display the data OUTSIDE the form logic
if st.session_state.extracted_data is not None:
    st.success("Extraction Complete!")
    st.dataframe(st.session_state.extracted_data, use_container_width=True)
    
    csv = st.session_state.extracted_data.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Data as CSV",
        data=csv,
        file_name='extracted_contracts.csv',
        mime='text/csv',
    )
