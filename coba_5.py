import pytesseract
from pdf2image import convert_from_path
from fuzzywuzzy import fuzz  # Pastikan sudah diinstall: pip install fuzzywuzzy

# Format yang diharapkan
expected_format = """SURAT PERINTAH TUGAS
Nomor :                 …………….

Menimbang	: 

Dasar		: 

Memberi Perintah :
Kepada 	1. Nama 	:
  NIP		:
  Jabatan	:

Untuk		:	1.


2.	Menjadi personil untuk menerima Username dan Password CPanel laman contoh.semarangkota.go.id di Dinas Komunikasi Statistik dan Persandian Kota Semarang
 Melaksanakan tugas dengan sebaik-baiknya.

"""

def normalize_text(text):
    """Menghapus spasi tambahan, enter, dan karakter kosong lainnya."""
    return ' '.join(text.split()).strip()

def extract_text_from_pdf(pdf_path):
    """Membaca teks dari PDF dengan OCR dan menormalisasinya."""
    images = convert_from_path(pdf_path)
    extracted_text = ' '.join([pytesseract.image_to_string(img) for img in images])
    return normalize_text(extracted_text)

def check_pdf_with_ocr(pdf_path, threshold=80):
    """Memeriksa kemiripan teks dalam PDF dengan format yang diharapkan."""
    extracted_text = extract_text_from_pdf(pdf_path)
    normalized_expected_format = normalize_text(expected_format)

    similarity = fuzz.partial_ratio(normalized_expected_format, extracted_text)

    print(f"Hasil OCR (Teks yang diekstrak):\n{extracted_text}")
    print(f"Tingkat Kemiripan: {similarity}%")

    if similarity >= threshold:
        print("✅ PDF Sesuai")
    else:
        print("❌ PDF Tidak Sesuai")

# Jalankan fungsi dengan path PDF yang sesuai
pdf_path = 'C:\PKL\Surat_Perintah.pdf'
check_pdf_with_ocr(pdf_path)
