import pandas as pd
import os
import re
from datetime import datetime
from dateutil import parser
INPUT_DIR = "data"
OUTPUT_PATH = "output/standardized_output18.csv"

# ------------------------
# Helpers
# ------------------------

def parse_amount(value):
    if pd.isna(value) or str(value).strip() == "":
        return 0, 0, "INR"  # return debit, credit, currency

    value_str = str(value).strip().lower()
    parts = value_str.split()
    is_credit = 'cr' in value_str.lower()

    amount_part = None
    for part in parts:
        if re.search(r'[\d.,]+', part):
            amount_part = part
            break

    if not amount_part:
        return 0, 0, "INR"

    amt = float(re.sub(r"[^\d.]", "", amount_part))

    return (0 if is_credit else amt), (amt if is_credit else 0), "INR"

def normalize_date(value):
    print(f"Normalizing date: {value}")
    try:
        dt = parser.parse(str(value), dayfirst=True)  # Day comes first for Indian-style dates
        return dt.strftime("%d-%m-%Y")
    except Exception as e:
        return None

def detect_transaction_type(description):
    if not isinstance(description, str):
        return "Domestic"
    intl_keywords = ['USD', 'EUR', 'DOLLAR', 'BERLIN', 'NEWYORK', 'CALIFORNIA', 'KATUNAYAKE']
    return "International" if any(word.lower() in description.lower() for word in intl_keywords) else "Domestic"

def extract_location_and_currency(description):
    if not isinstance(description, str):
        return "", "INR"

    words = description.strip().split()
    if not words:
        return "", "INR"

    currency_codes = {"USD", "EUR", "GBP", "AUD", "CAD", "SGD", "JPY", "CHF", "CNY"}
    last_word = words[-1].upper()

    if last_word in currency_codes:
        location = words[-2] if len(words) >= 2 else ""
        currency = last_word
    else:
        location = last_word
        currency = "INR"

    return location, currency

def detect_header_row(df):
    header_keywords = ['date', 'description', 'amount', 'debit', 'credit', 'transaction','amount']
    max_matches = 0
    header_index = 0

    for i in range(min(10, len(df))):
        row = df.iloc[i]
        match_count = sum(1 for cell in row if any(k in str(cell).lower() for k in header_keywords))
        if match_count > max_matches:
            max_matches = match_count
            header_index = i

    return header_index

# ------------------------
# Main Logic
# ------------------------

def process_files():
    records = []

    for filename in os.listdir(INPUT_DIR):
        filepath = os.path.join(INPUT_DIR, filename)
        if not os.path.isfile(filepath):
            continue

        print(f"📄 Processing: {filename}")

        try:
            if filename.endswith('.csv'):
                raw_df = pd.read_csv(filepath, header=None, engine='python')
            elif filename.endswith('.xlsx'):
                raw_df = pd.read_excel(filepath, header=None)
            elif filename.endswith('.txt'):
                raw_df = pd.read_fwf(filepath, header=None)
            else:
                continue
        except Exception as e:
            print(f"❌ Failed to read {filename}: {e}")
            continue

        header_idx = detect_header_row(raw_df)

        try:
            if filename.endswith('.csv'):
                df = pd.read_csv(filepath, skiprows=header_idx, engine='python')
            elif filename.endswith('.xlsx'):
                df = pd.read_excel(filepath, skiprows=header_idx)
            elif filename.endswith('.txt'):
                df = pd.read_fwf(filepath, skiprows=header_idx)
        except Exception as e:
            print(f"❌ Failed to re-read with detected header at row {header_idx}: {e}")
            continue

        df.fillna("", inplace=True)
        current_cardholder = None

        for _, row in df.iterrows():
            row_str = " ".join(str(x) for x in row.values)
            if re.match(r"^\s*(Rahul|Ritu|Rajat|Raj)\s*$", row_str):
                current_cardholder = row_str.strip()
                continue

            date = None
            description = ""
            debit, credit = 0, 0
            currency = "INR"

            for col in df.columns:
                val = str(row[col]).strip()

                if not date:
                    parsed_date = normalize_date(val)
                    if parsed_date:
                        date = parsed_date

                elif "transaction" in col.lower() or "description" in col.lower() or "details" in col.lower():
                    if not description:
                        description = val

                elif "amount" in col.lower():
                    debit, credit, currency = parse_amount(row[col])

                elif "credit" in col.lower() and "amount" not in col.lower():
                    try:
                        credit = float(re.sub(r"[^\d.]", "", str(row[col])))
                    except:
                        credit = 0

                elif "debit" in col.lower() and "amount" not in col.lower():
                    try:
                        debit = float(re.sub(r"[^\d.]", "", str(row[col])))
                    except:
                        debit = 0

            if re.match(r"^\d+$", description.strip()):
                if float(description.strip()) > 0 and credit == 0 and debit == 0:
                    credit = float(description.strip())
                description = ""

            if not description:
                for val in row.values:
                    val_str = str(val).strip()
                    if not val_str:
                        continue
                    if re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', val_str):
                        continue
                    if re.fullmatch(r"[\d.,]+", val_str):
                        continue
                    description = val_str
                    break

            if date and (credit or debit) and current_cardholder:
                txn_type = detect_transaction_type(description)
                location, currency = extract_location_and_currency(description)

                records.append({
                    "Date": date,
                    "Transaction Description": description,
                    "Debit": debit,
                    "Credit": credit,
                    "Currency": currency,
                    "CardName": current_cardholder,
                    "Transaction": txn_type,
                    "Location": location
                })

        df_final = pd.DataFrame(records)

        # Optional: Drop rows with invalid or missing dates (if any)
        df_final = df_final[df_final['Date'].notnull()]

        os.makedirs("output", exist_ok=True)
        df_final.to_csv(OUTPUT_PATH, index=False)
        print(f"\n✅ Output written to: {OUTPUT_PATH}")

if __name__ == "__main__":
    process_files()
