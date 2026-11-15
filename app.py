import streamlit as st
import pdfplumber
import pandas as pd
import re

st.set_page_config(page_title="Ejari Data Extractor", layout="wide")

def extract_rental_data(pdf_file):
    try:
        with pdfplumber.open(pdf_file) as pdf:
            all_words = []
            full_text = ""
            for page in pdf.pages:
                # Extract words with positional bounding boxes (x0, top, x1, bottom)
                words = page.extract_words()
                if words:
                    all_words.extend(words)
                
                # Raw text fallback
                txt = page.extract_text()
                if txt:
                    full_text += txt + "\n"
                    
    except Exception as e:
        return {"Filename": pdf_file.name, "Error": f"Could not read PDF: {str(e)}"}

    # Sort words spatially: top coordinate first, then left (x0) coordinate
    all_words = sorted(all_words, key=lambda w: (round(w['top'], 1), w['x0']))
    
    # Rebuild a clean, continuous text stream from sorted words
    reconstructed_text = " ".join([w['text'] for w in all_words])
    
    # Combine with raw text to ensure maximum coverage
    combined_corpus = reconstructed_text + "\n" + full_text
    clean_corpus = re.sub(r'[\|\r]+', ' ', combined_corpus)
    clean_corpus = re.sub(r'[ \t]+', ' ', clean_corpus)

    # Helper function to find text following specific keywords dynamically
    def get_val_after_keyword(keywords, pattern, text):
        for kw in keywords:
            # Look for keyword followed by anything up to our target regex pattern
            regex = re.escape(kw) + r'[\s\:\-\|]*(' + pattern + ')'
            match = re.search(regex, text, re.IGNORECASE)
            if match:
                val = match.group(1).strip()
                if val:
                    return val
        return None

    # 1. Property / Unit Number Extraction
    prop_no = get_val_after_keyword(
        ["Property No", "Property Nos", "Unit No", "Leased Unit", "رقم العقار"],
        r'[A-Z0-9]+-[A-Z0-9\-]+', 
        clean_corpus
    )
    if not prop_no:
        # Fallback search for common format like 205-5, 205-6 anywhere in text
        unit_match = re.search(r'\b(\d{1,4}-[A-Z0-9]+)\b', clean_corpus)
        prop_no = unit_match.group(1) if unit_match else "N/A"

    # 2. Start Date Extraction
    start_date = get_val_after_keyword(
        ["Start Date", "تاريخ البدء"],
        r'[\d]{2}-[\d]{2}-[\d]{4}', 
        clean_corpus
    ) or "N/A"

    # 3. End Date Extraction
    end_date = get_val_after_keyword(
        ["End Date", "تاريخ الإنتهاء"],
        r'[\d]{2}-[\d]{2}-[\d]{4}', 
        clean_corpus
    ) or "N/A"

    # 4. Actual Contract Amount (Handles standard AED and Unicode Greek Alpha 'ΑED')
    contract_amount = get_val_after_keyword(
        ["Actual Contract Amount", "المبلغ الفعلي العقد"],
        r'[\d,]+\.\d{2}', 
        clean_corpus
    )
    if contract_amount:
        contract_amount = f"{contract_amount} AED"
    else:
        # General currency pattern fallback
        amt_match = re.search(r'([\d,]+\.\d{2})\s*(?:AED|ΑED)', clean_corpus, re.IGNORECASE)
        contract_amount = f"{amt_match.group(1)} AED" if amt_match else "N/A"

    # 5. Emirates ID or Corporate Tenant Number
    tenant_id = get_val_after_keyword(
        ["Emirates ID", "Tenant No", "رقم المستأجر"],
        r'\d{5,15}', 
        clean_corpus
    )
    if not tenant_id:
        comp_match = re.search(r'(?:Tenant No|رقم المستأجر)[\s\:\-\|]*([A-Z0-9\-]+)', clean_corpus, re.IGNORECASE)
        tenant_id = comp_match.group(1) if comp_match else "N/A (Company/Not Found)"

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
