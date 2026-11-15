import streamlit as st
import pdfplumber
import pandas as pd
import re
import pytesseract
from pdf2image import convert_from_bytes
import io

st.set_page_config(page_title="Ejari Data Extractor", layout="wide")

def extract_rental_data(pdf_file):
    full_text = ""
    pdf_bytes = pdf_file.getvalue()
    
    try:
        # Step 1: Try standard pdfplumber extraction first
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text(layout=False)
                if txt:
                    full_text += txt + "\n"
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        for cell in row:
                            if cell:
                                full_text += str(cell).strip() + " "
    except Exception:
        pass

    # Step 2: If key data is missing or text is sparse, fallback to OCR automatically
    if "Start Date" not in full_text or "Actual Contract Amount" not in full_text or re.search(r'\b\d{1,4}-[A-Z0-9]+\b', full_text) is None:
        try:
            images = convert_from_bytes(pdf_bytes)
            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(img) + "\n"
            if ocr_text.strip():
                full_text += "\n" + ocr_text
        except Exception as e:
            print(f"OCR Error: {e}")

    # Clean up text stream
    clean_corpus = re.sub(r'[\|\r]+', ' ', full_text)
    clean_corpus = re.sub(r'[ \t]+', ' ', clean_corpus)

    # --- FIELD EXTRACTION LOGIC ---

    # 1. Property / Unit No (Handles 205-5, 205-6, etc.)
    prop_no = "N/A"
    unit_match = re.search(r'(?:Property No\.?\s*(?:\(s\))?|Unit No\.?\s*(?:\(s\))?|رقم العقار|Leased Unit)[:\s]*([A-Z0-9]+-[A-Z0-9\-]+)', clean_corpus, re.IGNORECASE)
    if unit_match:
        prop_no = unit_match.group(1).strip()
    else:
        # General fallback looking for standard unit string formats
        all_units = re.findall(r'\b(\d{1,4}-[A-Z0-9]+)\b', clean_corpus)
        if all_units:
            prop_no = all_units[0]

    # 2. Start Date
    start_date = "N/A"
    start_match = re.search(r'(?:Start Date|تاريخ البدء)[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', clean_corpus, re.IGNORECASE)
    if start_match:
        start_date = start_match.group(1)

    # 3. End Date
    end_date = "N/A"
    end_match = re.search(r'(?:End Date|تاريخ الإنتهاء)[:\s]*([\d]{2}-[\d]{2}-[\d]{4})', clean_corpus, re.IGNORECASE)
    if end_match:
        end_date = end_match.group(1)

    # 4. Actual Contract Amount (Handles standard AED and Greek Alpha 'ΑED')
    contract_amount = "N/A"
    amount_match = re.search(r'(?:Actual Contract Amount|المبلغ الفعلي العقد)[:\s]*([\d,]+\.\d{2})', clean_corpus, re.IGNORECASE)
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
        with st.spinner(f"Processing {len(uploaded_files)} files with OCR fallback..."):
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
