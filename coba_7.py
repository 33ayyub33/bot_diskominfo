import difflib
import pytesseract
from pdf2image import convert_from_path

# Format yang diharapkan
expected_sections = [
    "SURAT PERINTAH TUGAS",
    "Menimbang",
    "Dasar",
    "Memberi Perintah",
    "Kepada",
    "Nama",
    "NIP",
    "Jabatan",
    "Untuk",
    "Menjadi personil untuk menerima Username dan Password CPanel laman contoh.semarangkota.go.id di Dinas Komunikasi Statistik dan Persandian Kota Semarang",
    "Melaksanakan tugas dengan sebaik-baiknya."
]

def normalize_text(text):
    """Menghapus spasi tambahan, enter, dan karakter kosong lainnya."""
    return ' '.join(text.split()).strip()

def extract_text_from_pdf(pdf_path):
    """Membaca teks dari PDF dengan OCR dan menormalisasinya."""
    images = convert_from_path(pdf_path)
    extracted_text = ' '.join([pytesseract.image_to_string(img) for img in images])
    return normalize_text(extracted_text)

def check_pdf_with_ocr(pdf_path, threshold=70):
    """Memeriksa apakah teks dalam PDF sesuai dengan format yang diharapkan."""
    extracted_text = extract_text_from_pdf(pdf_path)

    # Bandingkan tiap bagian dengan difflib
    matching_scores = []
    for section in expected_sections:
        score = difflib.SequenceMatcher(None, section, extracted_text).ratio() * 100
        matching_scores.append(score)
    
    avg_similarity = sum(matching_scores) / len(matching_scores)

    print(f"Hasil OCR (Teks yang diekstrak):\n{extracted_text}")
    print(f"Tingkat Kemiripan Rata-rata: {avg_similarity:.2f}%")

    if avg_similarity >= threshold:
        print("✅ PDF Sesuai")
    else:
        print("❌ PDF Tidak Sesuai")

# Jalankan fungsi
pdf_path = r'C:\PKL\surat_1.pdf'
check_pdf_with_ocr(pdf_path)
