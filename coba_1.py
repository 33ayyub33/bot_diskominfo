import pdfplumber

# Format yang diharapkan
expected_format = """Ujian Akhir Semester Genap 2021/2022
Departemen Informatika/ Ilmu Komputer
FSM UNDIP Semarang
Mata Kuliah : Sistem Cerdas
Dosen : Sukmawati Nur Endah, S.Si, M.Kom - Khadijah, S.Si. M.Cs
Beban : 3 SKS
Sifat : Open Book
Hari/Tgl : Selasa / 14 Juni 2022
Waktu : 07.30 – 09.10"""


def check_pdf_format(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]  # Ambil halaman pertama
        text = page.extract_text()  # Ekstrak teks
        
        if expected_format in text:
            print("PDF Sesuai")
        else:
            print("PDF Tidak Sesuai")

# Ganti 'path/to/your/file.pdf' dengan path ke file PDF yang ingin diperiksa
check_pdf_format('C:/KULIAH/PKL/Bot/First/Second/Coba_OCR/Doc1.pdf')