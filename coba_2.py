import pytesseract
from pdf2image import convert_from_path

# Format yang diharapkan
expected_format = """Ujian Akhir Semester Genap 2021/2022
# Departemen Informatika/ Ilmu Komputer
# FSM UNDIP Semarang
# Mata Kuliah : Sistem Cerdas
# Dosen : Sukmawati Nur Endah, S.Si, M.Kom - Khadijah, S.Si. M.Cs
# Beban : 3 SKS
# Sifat : Open Book
# Hari/Tgl : Selasa / 14 Juni 2022
# Waktu : 07.30 – 09.10"""

def normalize_text(text):
    # Menghapus spasi tambahan dan karakter baru
    return ' '.join(text.split()).strip()

def check_pdf_with_ocr(pdf_path):
    # Mengonversi PDF ke gambar
    images = convert_from_path(pdf_path)
    
    # Mengambil teks dari setiap halaman
    extracted_text = ""
    for img in images:
        extracted_text += pytesseract.image_to_string(img)

    # Normalisasi teks
    normalized_text = normalize_text(extracted_text)
    print(normalized_text)
    normalized_expected_format = normalize_text(expected_format)

    if normalized_expected_format in normalized_text:
        print("PDF Sesuai")
    else:
        print("PDF Tidak Sesuai")

# Ganti 'path/to/your/file.pdf' dengan path ke file PDF yang ingin diperiksa
check_pdf_with_ocr('C:/KULIAH/PKL/Bot/First/Second/Coba_OCR/Doc1.pdf')