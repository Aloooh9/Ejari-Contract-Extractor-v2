import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Ejari Data Extractor", layout="wide")

def extract_rental_data(pdf_file):
    text = ""
    try:
        # Extract text from all pages
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        return {"Filename": pdf_file.name, "Error": f"Could not read PDF: {str(e)}"}

    # --- ROBUST REGEX PATTERNS (Supporting Old & New Formats) ---

    # 1. Property / Unit No (Handles standard labels and new tabular layouts)
    prop_no_match = re.search(r'(?:Property No\.(?:s)?|Unit No(?:\.\(s\))?|رقم العقار).*?\n\s*([A-Z0-9\-]+)', text, re.IGNORECASE)
    if not prop_no_match:
        # Fallback for new table structure where unit numbers appear right above property types
        prop_no_match = re.search(r'((?:[A-Z0-9]+\-)?[A-Z0-9]+)\s*\n\s*(?:Office|Shop|Apartment|Residential|Commercial)', text, re.IGNORECASE)

    # 2. Start Date & End Date (Tolerates spaces, newlines, and table pipes)
    start_date_match = re.search(r'Start Date[\s\n\|]*([\d]{2}-[\d]{2}-[\d]{4})', text, re.IGNORECASE)
    end_date_match = re.search(r'End Date[\s\n\|]*([\d]{2}-[\d]{2}-[\d]{4})', text, re.IGNORECASE)

    # 3. Actual Contract Amount (Handles standard 'AED' and Unicode Greek 'Α' variants)
    contract_amount_match = re.search(r'Actual Contract Amount[\s\n\|]*([\d,]+\.\d{2})\s*[A-ZΑ-Ωa-zα-ω]+', text, re.IGNORECASE)
    if not contract_amount_match:
        contract_amount_match = re.search(r'([\d,]+\.\d{2})\s*AED', text, re.IGNORECASE)

    # 4. Emirates ID or Corporate Tenant Number Fallback
    emirates_id_match = re.search(r'Emirates ID[\s\n\|]*(\d{15})', text, re.IGNORECASE)
    if not emirates_id_match:
        tenant_no_match = re.search(r'(?:Tenant No|رقم المستأجر)[\s\n\|]*([A-Z0-9]+)', text, re.IGNORECASE)
        tenant_identifier = tenant_no_match.group(1) if tenant_no_match else "N/A (Company/Not Found)"
    else:
        tenant_identifier = emirates_id_match.group(1)

    return {
        "Filename": pdf_file.name,
        "Property/Unit No": prop_no_match.group(1) if prop_no_match else "N/A",
        "Start Date": start_date_match.group(1) if start_date_match else "N/A",
        "End Date": end_date_match.group(1) if end_date_match else "N/A",
        "Actual Contract Amount": f"{contract_amount_match.group(1)} AED" if contract_amount_match else "N/A",
        "Emirates ID / Tenant No": tenant_identifier
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
            
            # Convert results to a DataFrame
            df = pd.DataFrame(results)
            
            st.success("Extraction Complete!")
            st.dataframe(df, use_container_width=True)
            
            # Convert DF to CSV for download
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name="extracted_rental_data.csv",
                mime="text/csv",
            )
