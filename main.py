import re
from typing import List
import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse

app = FastAPI(title="Ejari Contract Data Extractor")

def clean_extracted_value(value: str) -> str:
    if not value:
        return "NA"
    cleaned = value.strip().strip("/-")
    return cleaned if cleaned else "NA"

def parse_contract_text(text: str) -> dict:
    # Target regex strategies with NA defaults
    data = {
        "property_no": "NA",
        "start_date": "NA",
        "end_date": "NA",
        "contract_amount": "NA",
        "tenant_name": "NA",
        "emirates_id": "NA",
        "dewa_no": "NA"
    }

    # 1. Property No
    prop_match = re.search(r'(?:Property No\.(?:\(s\))?|رقم العقار)\s*[\(\)\s]*\s*(\d+)', text, re.IGNORECASE)
    if prop_match:
        data["property_no"] = clean_extracted_value(prop_match.group(1))

    # 2. Start Date
    start_match = re.search(r'Start Date\s*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
    if start_match:
        data["start_date"] = clean_extracted_value(start_match.group(1))

    # 3. End Date
    end_match = re.search(r'End Date\s*(\d{2}[-/]\d{2}[-/]\d{4})', text, re.IGNORECASE)
    if end_match:
        data["end_date"] = clean_extracted_value(end_match.group(1))

    # 4. Actual Contract Amount (with fallbacks)
    amount_match = re.search(r'Actual Contract Amount\s*([\d,.]+)', text, re.IGNORECASE)
    if not amount_match:
        amount_match = re.search(r'Contract Value AED\s*([\d,./-]+)', text, re.IGNORECASE)
    if not amount_match:
        amount_match = re.search(r'Contract Amount\s*([\d,.]+)', text, re.IGNORECASE)
        
    if amount_match:
        val = amount_match.group(1).replace(",", "").strip().strip("/-")
        data["contract_amount"] = f"{val} AED" if val else "NA"

    # 5. Tenant Name
    tenant_match = re.search(r'Tenant Name\s+([A-Za-z\s]+?)(?=\n|Tenant Email|Nationality|اسم المستاجر|Tenant No)', text, re.IGNORECASE)
    if tenant_match:
        data["tenant_name"] = clean_extracted_value(tenant_match.group(1))

    # 6. Emirates ID
    eid_match = re.search(r'(?:Emirates ID|رقم الهوية)\s*(\d{15})', text, re.IGNORECASE)
    if eid_match:
        data["emirates_id"] = clean_extracted_value(eid_match.group(1))

    # 7. DEWA Premise No
    dewa_match = re.search(r'(?:DEWA Premise No\.|Premises No \(DEWA\)|رقم ديوا)[\s\./]*\s*(\d{9,})', text, re.IGNORECASE)
    if dewa_match:
        data["dewa_no"] = clean_extracted_value(dewa_match.group(1))

    return data

@app.post("/api/extract")
async def extract_data(files: List[UploadFile] = File(...)):
    output_results = []
    for file in files:
        try:
            file_bytes = await file.read()
            # Instant low-memory parsing using PyMuPDF
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            full_text = ""
            for page in doc:
                full_text += page.get_text() + "\n"
            doc.close()
            
            parsed_meta = parse_contract_text(full_text)
            parsed_meta["filename"] = file.filename
            output_results.append(parsed_meta)
        except Exception:
            output_results.append({
                "filename": file.filename,
                "property_no": "NA",
                "start_date": "NA",
                "end_date": "NA",
                "contract_amount": "NA",
                "tenant_name": "NA",
                "emirates_id": "NA",
                "dewa_no": "NA"
            })
    return output_results

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Tenancy Contract Extractor</title>
        <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    </head>
    <body class="bg-slate-50 text-slate-800 min-h-screen font-sans">
        <div class="max-w-6xl mx-auto px-4 py-8">
            <header class="mb-8 border-b border-slate-200 pb-4">
                <h1 class="text-3xl font-bold text-slate-900">📄 Ejari Contract Parser</h1>
                <p class="text-slate-500 mt-1">Upload tenancy PDFs to extract data profiles. Missing elements will default to 'NA'.</p>
            </header>

            <div class="bg-white p-6 rounded-xl shadow-sm border border-slate-200 mb-8">
                <form id="uploadForm" class="space-y-4">
                    <label class="block text-sm font-semibold text-slate-700">Select Multiple PDF Files</label>
                    <input type="file" id="fileInput" multiple accept=".pdf" 
                        class="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 border border-slate-300 rounded-md p-2" />
                    <button type="submit" id="submitBtn" 
                        class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-5 rounded-md transition duration-150 inline-flex items-center space-x-2 cursor-pointer">
                        <span>Process Data Profiles</span>
                    </button>
                </form>
            </div>

            <div id="loading" class="hidden text-center py-6 text-slate-500 font-medium">
                Parsing batch upload... Please hold.
            </div>

            <div id="resultsWrapper" class="hidden space-y-4">
                <div class="flex justify-between items-center">
                    <h2 class="text-xl font-bold text-slate-900">Extracted Metrics</h2>
                    <button id="downloadBtn" class="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium py-1.5 px-4 rounded-md transition duration-150 cursor-pointer">
                        📥 Export to CSV
                    </button>
                </div>
                <div class="overflow-x-auto rounded-lg border border-slate-200 shadow-sm bg-white">
                    <table class="min-w-full divide-y divide-slate-200 text-left text-sm" id="resultsTable">
                        <thead class="bg-slate-100 font-semibold text-slate-700">
                            <tr>
                                <th class="p-4">Filename</th>
                                <th class="p-4">Property No</th>
                                <th class="p-4">Start Date</th>
                                <th class="p-4">End Date</th>
                                <th class="p-4">Amount</th>
                                <th class="p-4">Tenant Name</th>
                                <th class="p-4">Emirates ID</th>
                                <th class="p-4">DEWA Premise</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-200"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <script>
            let parsedGlobalDataset = [];
            const form = document.getElementById('uploadForm');
            const fileInput = document.getElementById('fileInput');
            const submitBtn = document.getElementById('submitBtn');
            const loading = document.getElementById('loading');
            const resultsWrapper = document.getElementById('resultsWrapper');
            const tableBody = document.querySelector('#resultsTable tbody');
            const downloadBtn = document.getElementById('downloadBtn');

            form.addEventListener('submit', async (e) => {
                e.preventDefault();
                if (!fileInput.files.length) return alert('Please select files first.');

                loading.classList.remove('hidden');
                resultsWrapper.classList.add('hidden');
                submitBtn.disabled = true;

                const formData = new FormData();
                for (let file of fileInput.files) {
                    formData.append('files', file);
                }

                try {
                    const response = await fetch('/api/extract', { method: 'POST', body: formData });
                    parsedGlobalDataset = await response.json();
                    
                    tableBody.innerHTML = '';
                    parsedGlobalDataset.forEach(row => {
                        const tr = document.createElement('tr');
                        tr.className = "hover:bg-slate-50 transition";
                        tr.innerHTML = `
                            <td class="p-4 font-medium text-slate-900 max-w-xs truncate">${row.filename}</td>
                            <td class="p-4">${row.property_no}</td>
                            <td class="p-4">${row.start_date}</td>
                            <td class="p-4">${row.end_date}</td>
                            <td class="p-4 font-mono">${row.contract_amount}</td>
                            <td class="p-4">${row.tenant_name}</td>
                            <td class="p-4 font-mono">${row.emirates_id}</td>
                            <td class="p-4 font-mono">${row.dewa_no}</td>
                        `;
                        tableBody.appendChild(tr);
                    });
                    resultsWrapper.classList.remove('hidden');
                } catch (err) {
                    alert('An unexpected exception occurred while parsing files.');
                } finally {
                    loading.classList.add('hidden');
                    submitBtn.disabled = false;
                }
            });

            downloadBtn.addEventListener('click', () => {
                if (!parsedGlobalDataset.length) return;
                const headers = ["Filename", "Property No", "Start Date", "End Date", "Amount", "Tenant Name", "Emirates ID", "DEWA No"];
                const csvRows = [headers.join(',')];
                
                parsedGlobalDataset.forEach(item => {
                    const values = [
                        `"${item.filename}"`,
                        `"${item.property_no}"`,
                        `"${item.start_date}"`,
                        `"${item.end_date}"`,
                        `"${item.contract_amount}"`,
                        `"${item.tenant_name}"`,
                        `"${item.emirates_id}"`,
                        `"${item.dewa_no}"`
                    ];
                    csvRows.push(values.join(','));
                });

                const blob = new Blob([csvRows.join('\\n')], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.setAttribute('href', url);
                a.setAttribute('download', 'extracted_contracts.csv');
                a.click();
            });
        </script>
    </body>
    </html>
    """
