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
                # Extract standard text layout
                extracted = page.extract_text(layout=False)
                if extracted:
                    text += extracted + "\n"
                
                # Extract explicit tables to catch grid/tabular cells cleanly
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_text = " ".join([str(cell) for cell in row if cell])
                        text += row_text + "\n"
                        
    except Exception as e:
        return {"Filename": pdf_file.name, "Error": f"Could not read PDF: {str(e)}"}

    # Clean up whitespace and vertical table dividers
    cleaned_text = re.sub(r'[\|\r]+', ' ', text)
    cleaned_text = re.sub(r'[ \t]+', ' ', cleaned_text)

    # 1. Property / Unit No (Handles new layouts like 205-6, 205-5, etc.)
    prop_no = "N/A"
    prop_match = re.search(r'(?:Property No\.?\s*(?:\(s\))?|رقم العقار|Leased Unit)[:\s]*([A-Z0-9]+-[A-Z0-9\-]+)', cleaned_text, re.IGNORECASE)
    if prop_match:
        prop_no = prop_match.group(1).strip()
    else:
        # Fallback: scan for standard unit number formats (e.g. 205-6)
        unit_fallbacks = re.findall(r'\b(\d{1,4}-[A-Z0-9]+)\b', cleaned_text)
        if unit_fallbacks:
            prop_no = unit_fallbacks[0]

    # 2. Start Date
    start_date = "N/A"
    start_match = re.search(r'Start Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', cleaned_text, re.IGNORECASE)
    if start_match:
        start_date = start_match.group(1)

    # 3. End Date
    end_date = "N/A"
    end_match = re.search(r'End Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', cleaned_text, re.IGNORECASE)
    if end_match:
        end_date = end_match.group(1)

    # 4. Actual Contract Amount (Handles standard AED and Unicode Greek Alpha 'ΑED')
    contract_amount = "N/A"
    amount_match = re.search(r'Actual Contract Amount[:\s]*([\d,]+\.\d{2})\s*[A-ZΑ-Ωa-zα-ω]*', cleaned_text, re.IGNORECASE)
    if amount_match:
        contract_amount = f"{amount_match.group(1)} AED"
    else:
        gen_amount = re.search(r'([\d,]+\.\d{2})\s*(?:AED|ΑED)', cleaned_text, re.IGNORECASE)
        if gen_amount:
            contract_amount = f"{gen_amount.group(1)} AED"

    # 5. Emirates ID or Corporate Tenant Number
    tenant_id = "N/A (Company/Not Found)"
    eid_match = re.search(r'Emirates ID[:\s]*(\d{15})', cleaned_text, re.IGNORECASE)
    if eid_match:
        tenant_id = eid_match.group(1)
    else:
        tenant_no_match = re.search(r'(?:Tenant No|رقم المستأجر)[:\s]*(\d{5,15})', cleaned_text, re.IGNORECASE)
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
                mime="text/csv",
            )
