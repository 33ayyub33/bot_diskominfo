import os
import pytesseract
from pdf2image import convert_from_path

# Pastikan path Tesseract sudah diatur dengan benar
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\asus\AppData\Local\Programs\Tesseract-OCR"

def normalize_text(text):
    """Menghapus spasi tambahan dan karakter baru."""
    return ' '.join(text.split()).strip()

def extract_text_from_pdf(pdf_path):
    """Mengonversi PDF ke gambar lalu mengekstrak teks dengan OCR."""
    try:
        images = convert_from_path(pdf_path)
        extracted_text = ""

        for img in images[:1]:  # Hanya ambil halaman pertama
            extracted_text += pytesseract.image_to_string(img)

        return normalize_text(extracted_text)
    
    except Exception as e:
        print(f"⚠️ Error saat memproses {pdf_path}: {str(e)}")
        return None

def compare_pdfs(template_pdf, target_pdf):
    """Membandingkan teks header PDF target dengan PDF template."""
    template_text = extract_text_from_pdf(template_pdf)
    target_text = extract_text_from_pdf(target_pdf)

    if template_text and target_text:
        if template_text in target_text:
            print(f"✅ {os.path.basename(target_pdf)}: PDF Sesuai")
        else:
            print(f"❌ {os.path.basename(target_pdf)}: PDF Tidak Sesuai")
    else:
        print(f"⚠️ Gagal membandingkan {os.path.basename(target_pdf)}")

def check_pdfs_in_folder(folder_path, template_pdf):
    """Mengecek semua PDF dalam folder, membandingkan dengan template."""
    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith(".pdf") and file_name != os.path.basename(template_pdf):
            target_pdf = os.path.join(folder_path, file_name)
            compare_pdfs(template_pdf, target_pdf)

# Ganti dengan path PDF A (template) dan folder yang berisi PDF B
template_pdf = r"C:\PKL\Doc1.pdf" 
folder_path = r"C:\PKL\Coba_OCR"

check_pdfs_in_folder(folder_path, template_pdf)
