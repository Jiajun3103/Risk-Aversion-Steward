from fpdf import FPDF

def create_example_invoice():
    pdf = FPDF()
    pdf.add_page()
    
    # 标题
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 20, "SALES INVOICE", ln=True, align='C')
    
    # 发票信息
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Invoice No: INV-2026-001", ln=True)
    pdf.cell(0, 10, "Date: April 24, 2026", ln=True)
    pdf.cell(0, 10, "Customer: Tech Solution Co.", ln=True)
    pdf.ln(10)
    
    # 表头
    pdf.set_fill_color(200, 220, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(40, 10, "SKU", 1, 0, 'C', True)
    pdf.cell(100, 10, "Product Name", 1, 0, 'C', True)
    pdf.cell(30, 10, "Qty", 1, 1, 'C', True)
    
    # 这里的 SKU 必须匹配你数据库里的数据
    items = [
        ("SKU-1024", "Wireless Earbuds Pro", "5"),
        ("SKU-3099", "USB-C Fast Charger", "10"),
        ("SKU-2048", "Mechanical Keyboard", "2")
    ]
    
    pdf.set_font("Arial", size=12)
    for sku, name, qty in items:
        pdf.cell(40, 10, sku, 1)
        pdf.cell(100, 10, name, 1)
        pdf.cell(30, 10, qty, 1, 1, 'C')
        
    pdf.ln(20)
    pdf.cell(0, 10, "Total Amount: $1,250.00", ln=True, align='R')
    
    pdf.output("test_invoice.pdf")
    print("✅ Successfully generated 'test_invoice.pdf'!")

if __name__ == "__main__":
    create_example_invoice()