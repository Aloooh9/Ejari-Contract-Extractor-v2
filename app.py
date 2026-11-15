import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Ejari Data Extractor", layout="wide")

def extract_rental_data(pdf_file):
    full_text = ""
    table_cells = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # 1. Extract standard text
                txt = page.extract_text(layout=False)
                if txt:
                    full_text += txt + "\n"
                
                # 2. Extract structured table rows/cells explicitly
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        for cell in row:
                            if cell:
                                cleaned_cell = str(cell).strip().replace("\n", " ")
                                table_cells.append(cleaned_cell)
                                full_text += cleaned_cell + "\n"
                                
    except Exception as e:
        return {"Filename": pdf_file.name, "Error": f"Could not read PDF: {str(e)}"}

    # Normalize text stream
    clean_corpus = re.sub(r'[\|\r]+', ' ', full_text)
    clean_corpus = re.sub(r'[ \t]+', ' ', clean_corpus)

    # --- FIELD EXTRACTION LOGIC ---

    # 1. Property / Unit No (Targeting explicit table cell patterns like 205-5, 205-6)
    prop_no = "N/A"
    # Search specifically inside isolated table cells first
    for i, cell in enumerate(table_cells):
        if re.search(r'(?:Property No|Unit No|رقم العقار)', cell, re.IGNORECASE):
            # The value is usually in the next cell or row index
            if i + 1 < len(table_cells):
                candidate = table_cells[i + 1]
                if re.match(r'^[A-Z0-9]+(-[A-Z0-9]+)+$', candidate):
                    prop_no = candidate
                    break
    
    # Fallback pattern match in full text stream if table cell scan misses it
    if prop_no == "N/A":
        unit_match = re.search(r'\b(\d{1,4}-[A-Z0-9]+)\b', clean_corpus)
        if unit_match:
            prop_no = unit_match.group(1)

    # 2. Start Date
    start_date = "N/A"
    start_match = re.search(r'Start Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', clean_corpus, re.IGNORECASE)
    if start_match:
        start_date = start_match.group(1)

    # 3. End Date
    end_date = "N/A"
    end_match = re.search(r'End Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', clean_corpus, re.IGNORECASE)
    if end_match:
        end_date = end_match.group(1)

    # 4. Actual Contract Amount (handles standard AED and Unicode Greek Alpha 'ΑED')
    contract_amount = "N/A"
    amount_match = re.search(r'Actual Contract Amount[:\s]*([\d,]+\.\d{2})', clean_corpus, re.IGNORECASE)
    if not amount_match:
        amount_match = re.search(r'([\d,]+\.\d{2})\s*(?:AED|ΑED)', clean_corpus, re.IGNORECASE)
    
    if amount_match:
        contract_amount = f"{amount_match.group(1)} AED"

    # 5. Emirates ID or Corporate Tenant Number
    tenant_id = "N/A (Company/Not Found)"
    eid_match = re.search(r'Emirates ID[:\s]*(\d{15})', clean_corpus, re.IGNORECASE)
    if eid_match:
        tenant_id = eid_match.group(1)
    else:
        tenant_no_match = re.search(r'(?:Tenant No|رقم المستأجر)[:\s]*([A-Z0-9]{5,15})', clean_corpus, re.IGNORECASE)
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
