import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Ejari Data Extractor", layout="wide")

def extract_rental_data(pdf_file):
    words_list = []
    full_text = ""
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                # Extract words with coordinates for robust spatial/keyword matching
                page_words = page.extract_words()
                if page_words:
                    words_list.extend(page_words)
                
                # Extract text lines
                extracted = page.extract_text()
                if extracted:
                    full_text += extracted + "\n"
                
                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        row_str = " ".join([str(cell).strip() for cell in row if cell])
                        full_text += row_str + "\n"
                        
    except Exception as e:
        return {"Filename": pdf_file.name, "Error": f"Could not read PDF: {str(e)}"}

    # Normalize text (remove pipes, carriage returns, excessive spaces)
    clean_text = re.sub(r'[\|\r]+', ' ', full_text)
    clean_text = re.sub(r'[ \t]+', ' ', clean_text)

    # Helper function to find patterns using keywords
    def find_value(patterns, text):
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                if val and val.lower() != "nan":
                    return val
        return "N/A"

    # 1. Property / Unit No Patterns
    # Specifically targeting patterns like "205-6", "205-5", etc., near property keywords or table cells
    prop_patterns = [
        r'(?:Property No\.?\s*(?:\(s\))?|Unit No\.?\s*(?:\(s\))?|رقم العقار|Leased Unit)[:\s]*([A-Z0-9\-]+)',
        r'\b(\d{1,4}-[A-Z0-9]+)\b',  # Matches formats like 205-6, 205-5
    ]
    prop_no = find_value(prop_patterns, clean_text)

    # 2. Start Date Patterns
    start_patterns = [
        r'Start Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})',
        r'تاريخ البدء[:\s]*([\d]{2}-[\d]{2}-[\d]{4})',
        r'([\d]{2}-[\d]{2}-[\d]{4})(?=\s*تاريخ الإنتهاء|\s*End Date)'
    ]
    start_date = find_value(start_patterns, clean_text)

    # 3. End Date Patterns
    end_patterns = [
        r'End Date[:\s]*([\d]{2}-[\d]{2}-[\d]{4})',
        r'تاريخ الإنتهاء[:\s]*([\d]{2}-[\d]{2}-[\d]{4})',
    ]
    end_date = find_value(end_patterns, clean_text)

    # 4. Actual Contract Amount Patterns (handles standard AED and Greek Alpha 'ΑED')
    contract_amount = "N/A"
    amount_match = re.search(r'Actual Contract Amount[:\s]*([\d,]+\.\d{2})', clean_text, re.IGNORECASE)
    if not amount_match:
        amount_match = re.search(r'([\d,]+\.\d{2})\s*(?:AED|ΑED)', clean_text, re.IGNORECASE)
    
    if amount_match:
        contract_amount = f"{amount_match.group(1)} AED"

    # 5. Tenant ID / Emirates ID / Tenant Number Patterns
    tenant_patterns = [
        r'Emirates ID[:\s]*(\d{15})',
        r'(?:Tenant No|رقم المستأجر)[:\s]*(\d{5,15})',
        r'(?:Tenant No|رقم المستأجر)[:\s]*([A-Z0-9\-]+)'
    ]
    tenant_id = find_value(tenant_patterns, clean_text)
    if tenant_id == "N/A":
        tenant_id = "N/A (Company/Not Found)"

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
