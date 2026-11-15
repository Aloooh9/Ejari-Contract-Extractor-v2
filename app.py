import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Ejari Data Extractor", layout="wide")

def extract_rental_data(pdf_file):
    text = ""
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return {"Filename": pdf_file.name, "Error": f"Could not read PDF: {str(e)}"}

    # Clean up excessive whitespace/pipes for easier matching
    cleaned_text = re.sub(r'[\|\r]', ' ', text)

    # 1. Property / Unit No Extraction
    prop_no = "N/A"
    # Try explicit labels first
    prop_match = re.search(r'(?:Property No\.?\s*(?:\(s\))?|Unit No\.?\s*(?:\(s\))?|رقم العقار)[:\s]*([A-Z0-9\-]+)', cleaned_text, re.IGNORECASE)
    if prop_match:
        prop_no = prop_match.group(1).strip()
    else:
        # Fallback: look for typical unit format (e.g., 205-5 or similar alphanumeric hyphenated codes)
        unit_fallbacks = re.findall(r'\b([A-Z0-9]+-[A-Z0-9\-]+)\b', cleaned_text)
        if unit_fallbacks:
            prop_no = unit_fallbacks[0]

    # 2. Start Date Extraction
    start_date = "N/A"
    start_match = re.search(r'Start Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', cleaned_text, re.IGNORECASE)
    if start_match:
        start_date = start_match.group(1)

    # 3. End Date Extraction
    end_date = "N/A"
    end_match = re.search(r'End Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', cleaned_text, re.IGNORECASE)
    if end_match:
        end_date = end_match.group(1)

    # 4. Actual Contract Amount Extraction (handles standard AED and Greek Alpha variant 'ΑED')
    contract_amount = "N/A"
    amount_match = re.search(r'Actual Contract Amount[:\s]*([\d,]+\.\d{2})\s*[A-ZΑ-Ωa-zα-ω]*', cleaned_text, re.IGNORECASE)
    if amount_match:
        contract_amount = f"{amount_match.group(1)} AED"
    else:
        # General fallback for any currency amount ending in AED
        general_amount = re.search(r'([\d,]+\.\d{2})\s*(?:AED|ΑED)', cleaned_text, re.IGNORECASE)
        if general_amount:
            contract_amount = f"{general_amount.group(1)} AED"

    # 5. Emirates ID or Tenant Number / License No
    tenant_id = "N/A (Company/Not Found)"
    eid_match = re.search(r'Emirates ID[:\s]*(\d{15})', cleaned_text, re.IGNORECASE)
    if eid_match:
        tenant_id = eid_match.group(1)
    else:
        tenant_no_match = re.search(r'(?:Tenant No|رقم المستأجر)[:\s]*([A-Z0-9]+)', cleaned_text, re.IGNORECASE)
        if tenant_no_match:
            tenant_id = tenant_no_match.group(1)

    return {
        "Filename": pdf_file.name,
        "Property/Unit No": prop_no,
        "Start Date": start_date,
        "End Date": end_date,
        "Actual Contract Amount": contract_amount,
        "Emirates ID / Tenant No": tenant_id
    }

# --- Web App UI ---
st.title("📄 Ejari Contract Extractor")
st.write("Upload your rental PDF files to extract key contract details into a downloadable table.")

uploaded_files = st.file_uploader("Upload PDF Files", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button("Extract Data"):
        with st.spinner(f"Processing {len(uploaded_files)} files..."):
            results = []
            for pdf_file in uploaded_files:
                data = extract_rental_data(pdf_file)
                results.append(data)
            
            df = pd.DataFrame(results)
            st.success("Extraction Complete!")
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name="extracted_rental_data.csv",
                mime="text/css" if False else "text/csv",
            )
