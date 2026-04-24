import pandas as pd
import docx

# --- 1. 生成测试用的 Excel 发票 (.xlsx) ---
def create_excel_invoice():
    data = {
        "SKU Code":["SKU-1024", "SKU-2048", "SKU-3099"],
        "Product Name":["Wireless Earbuds Pro", "Mechanical Keyboard", "USB-C Fast Charger"],
        "Quantity Sold": [10, 2, 8],
        "Unit Price": ["$35.00", "$120.00", "$15.00"]
    }
    df = pd.DataFrame(data)
    df.to_excel("test_invoice.xlsx", index=False)
    print("✅ 成功生成 Excel 发票: test_invoice.xlsx")

# --- 2. 生成测试用的 Word 发票 (.docx) ---
def create_word_invoice():
    doc = docx.Document()
    doc.add_heading('SALES INVOICE', 0)
    doc.add_paragraph('Invoice No: INV-2026-002')
    doc.add_paragraph('Date: April 25, 2026')
    doc.add_paragraph('Customer: Future Tech Corp\n')
    
    # 在 Word 中添加文字表格
    doc.add_heading('Order Details:', level=2)
    doc.add_paragraph('1. Wireless Earbuds Pro (SKU-1024) - Qty: 6')
    doc.add_paragraph('2. USB-C Fast Charger (SKU-3099) - Qty: 15')
    
    doc.save("test_invoice.docx")
    print("✅ 成功生成 Word 发票: test_invoice.docx")

if __name__ == "__main__":
    create_excel_invoice()
    create_word_invoice()