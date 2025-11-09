from typing import Final, List, Dict, Set
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import re
import json
from pytesseract import image_to_string
from pdf2image import convert_from_path
import tempfile
from PIL import Image
import PyPDF2

TOKEN: Final = '8116521602:AAFKMElIZp8RluE_4eqVchrdQZTCq-O_zUk'
BOT_USERNAME: Final = '@kominfoo_bot'

# Konfigurasi Google Drive dan Sheets
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = "1wdpE2wgn-OnFZ75LT3agsPCjzIjAVONXs-as63xGivo"
FOLDER_ID = "13XaW0qsyE6Cwcd6szdhbGfk4h32bgRnL"


# Konfigurasi Google Drive dan Sheets
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Mapping layanan dan langkah-langkahnya
LAYANAN_STEPS = {
    "Pengajuan Tanda Tangan Elektronik": ["Nama_Lengkap", "NIP_ASN", "NIK_KTP", "Nama_OPD", "Nomor_Handphone", "Alamat_Email", "Jabatan"],
    "Reset/Permintaan Akun Cpanel": ["Nama_Lengkap", "NIP_Pemohon", "Jabatan", "Asal_OPD", "URL_Aplikasi", "Surat_Tugas", "Syarat_dan_Ketentuan"],
    "Permohonan Video Conference": ["Nama_Lengkap", "NIP_Pemohon", "Nomor_Handphone", "Unit_Kerja", "Nama_Acara", "Tempat", "Tanggal_Mulai", "Tanggal_Selesai", "Waktu", "Estimasi_Jumlah_Partisipan", "Live_Youtube", "Permohonan_Bantuan", "Email_Dinas", "Informasi_Tambahan", "Surat_Permohonan"],
}

# Regex validasi untuk setiap langkah
VALIDASI_REGEX = {
    "Nama_Lengkap": r"^[A-Za-z\s\.]{3,50}$",
    "NIP_ASN": r"^\d{16}$",
    "NIP_Pemohon": r"^\d{16}$",
    "NIK_KTP": r"^\d{16}$",
    "Nama_OPD": r"^[A-Za-z\s\.\,\-]{3,100}$",
    "Asal_OPD": r"^[A-Za-z\s\.\,\-]{3,100}$",
    "Unit_Kerja": r"^[A-Za-z\s\.\,\-]{3,100}$",
    "Nomor_Handphone": r"^(\+62|62|0)8[1-9][0-9]{7,11}$",
    "Alamat_Email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "Email_Dinas": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "Jabatan": r"^[A-Za-z\s\.\,\-]{3,50}$",
    "URL_Aplikasi": r"^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%.\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%\+.~#?&//=]*)$",
    "Nama_Acara": r"^[A-Za-z0-9\s\.\,\-\(\)]{3,100}$",
    "Tempat": r"^[A-Za-z0-9\s\.\,\-\(\)]{3,100}$",
    "Tanggal_Mulai": r"^\d{2}\/\d{2}\/\d{4}$",
    "Tanggal_Selesai": r"^\d{2}\/\d{2}\/\d{4}$",
    "Waktu": r"^\d{2}:\d{2}(\s?-\s?\d{2}:\d{2})?$",
    "Estimasi_Jumlah_Partisipan": r"^\d{1,4}$",
    "Live_Youtube": r"^(Ya|Tidak)$",
    "Informasi_Tambahan": r"^.{0,200}$",
}

# Pesan validasi untuk setiap langkah
VALIDASI_MESSAGES = {
    "Nama_Lengkap": "Nama lengkap harus terdiri dari 3-50 karakter (huruf, spasi, titik).",
    "NIP_ASN": "NIP ASN harus terdiri dari 18 digit angka.",
    "NIP_Pemohon": "NIP Pemohon harus terdiri dari 18 digit angka.",
    "NIK_KTP": "NIK KTP harus terdiri dari 16 digit angka.",
    "Nama_OPD": "Nama OPD harus 3-100 karakter.",
    "Asal_OPD": "Asal OPD harus 3-100 karakter.",
    "Unit_Kerja": "Unit Kerja harus 3-100 karakter.",
    "Nomor_Handphone": "Format nomor handphone tidak valid. Contoh: 08123456789 atau +628123456789.",
    "Alamat_Email": "Format email tidak valid.",
    "Email_Dinas": "Format email dinas tidak valid.",
    "Jabatan": "Jabatan harus 3-50 karakter.",
    "URL_Aplikasi": "URL Aplikasi tidak valid. Contoh: https://example.com",
    "Nama_Acara": "Nama acara harus 3-100 karakter.",
    "Tempat": "Tempat harus 3-100 karakter.",
    "Tanggal_Mulai": "Format tanggal tidak valid. Gunakan format DD/MM/YYYY.",
    "Tanggal_Selesai": "Format tanggal tidak valid. Gunakan format DD/MM/YYYY.",
    "Waktu": "Format waktu tidak valid. Gunakan format HH:MM atau HH:MM - HH:MM.",
    "Estimasi_Jumlah_Partisipan": "Estimasi jumlah partisipan harus berupa angka (maksimal 4 digit).",
    "Live_Youtube": "Jawab dengan 'Ya' atau 'Tidak'.",
    "Informasi_Tambahan": "Informasi tambahan maksimal 200 karakter.",
}

# File steps - bagian yang memerlukan upload file
FILE_STEPS = {
    "Reset/Permintaan Akun Cpanel": ["Surat_Tugas"],
    "Permohonan Video Conference": ["Surat_Permohonan"]
}

# Multiple choice options untuk langkah tertentu
MULTIPLE_CHOICE_STEPS = {
    "Permohonan Video Conference": {
        "Permohonan_Bantuan": ["Link online meeting/vidcon", "Pinjam peralatan vidcon", "Personil/operator"]
    }
}

# Syarat dan Ketentuan per layanan
SYARAT_DAN_KETENTUAN = {
    "Reset/Permintaan Akun Cpanel": """
Dengan menggunakan layanan ini, Anda setuju untuk:
1. Bertanggung jawab penuh atas keamanan akun Cpanel
2. Tidak membagikan kredensial akun kepada pihak yang tidak berwenang
3. Menggunakan akun hanya untuk keperluan resmi instansi
4. Mematuhi semua kebijakan keamanan informasi yang berlaku
5. Melaporkan segera jika terjadi aktivitas mencurigakan pada akun

Apakah Anda setuju dengan syarat dan ketentuan di atas?
"""
}

# Required keywords for each document type (OCR verification)
REQUIRED_KEYWORDS = {
    "Surat_Tugas": ["surat tugas", "yang bertanda tangan", "menugaskan", "kepada", "untuk"],
    "Surat_Permohonan": ["surat permohonan", "dengan hormat", "permohonan", "demikian", "terima kasih"]
}

# Minimum keyword matches required to consider document valid
MIN_KEYWORD_MATCHES = 3

spreadsheet = client.open_by_key(SPREADSHEET_ID)  # Ambil objek Spreadsheet

def save_to_google_sheets(user_data, service_name):
    try:
        # Coba mendapatkan worksheet yang sudah ada
        worksheet = spreadsheet.worksheet(service_name)
    except gspread.exceptions.WorksheetNotFound:
        # Jika tidak ada, buat worksheet baru
        worksheet = spreadsheet.add_worksheet(title=service_name, rows="1000", cols="20")
        
        # Tambahkan header jika ini worksheet baru
        header_row = LAYANAN_STEPS[service_name]
        worksheet.append_row(header_row)
    
    # Ambil data dalam urutan yang sesuai dengan langkah-langkah layanan
    row = [user_data.get(key, "") for key in LAYANAN_STEPS[service_name]]
    worksheet.append_row(row)
    return True

# Fungsi yang lebih aman untuk menghapus file sementara
def delete_temp_file(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} berhasil dihapus")
    except PermissionError:
        print(f"Tidak bisa menghapus {file_path} - file sedang digunakan")
    except Exception as e:
        print(f"Error saat menghapus {file_path}: {str(e)}")

# Fungsi untuk validasi input berdasarkan regex
def validate_input(input_text, step_name):
    if step_name not in VALIDASI_REGEX:
        return True, ""  # Tidak ada validasi untuk langkah ini
    
    pattern = VALIDASI_REGEX[step_name]
    if re.match(pattern, input_text):
        return True, ""
    else:
        return False, VALIDASI_MESSAGES.get(step_name, f"Format input untuk {step_name.replace('_', ' ')} tidak valid.")

# Fungsi untuk menangani perintah start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bersihkan user_data untuk memulai layanan baru
    context.user_data.clear()
    
    keyboard = [[service] for service in LAYANAN_STEPS.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Silakan pilih salah satu layanan berikut:', reply_markup=reply_markup)

# Cek apakah langkah ini memerlukan file
def is_file_step(service, step_name):
    return service in FILE_STEPS and step_name in FILE_STEPS[service]

# Cek apakah langkah ini memerlukan pilihan ganda
def is_multiple_choice_step(service, step_name):
    return service in MULTIPLE_CHOICE_STEPS and step_name in MULTIPLE_CHOICE_STEPS[service]

# Cek apakah langkah ini adalah syarat dan ketentuan
def is_terms_step(step_name):
    return step_name == "Syarat_dan_Ketentuan"

# Fungsi untuk menampilkan pilihan multiple choice dengan kemampuan memilih banyak
async def show_multiple_choice_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    selected_service = user_data['selected_service']
    step_index = user_data['step_index']
    current_step = LAYANAN_STEPS[selected_service][step_index]
    
    # Cek jika sudah ada pilihan yang dipilih sebelumnya
    if f"{current_step}_selected" not in user_data:
        user_data[f"{current_step}_selected"] = set()
    
    # Dapatkan opsi yang tersedia
    choices = MULTIPLE_CHOICE_STEPS[selected_service][current_step]
    
    # Prepare keyboard dengan status pilihan
    keyboard = []
    for choice in choices:
        prefix = "✅ " if choice in user_data[f"{current_step}_selected"] else "⬜ "
        keyboard.append([f"{prefix}{choice}"])
    
    # Tambahkan tombol "Selesai" untuk konfirmasi pilihan
    keyboard.append(["✓ Selesai Memilih"])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"Pilih {current_step.replace('_', ' ')} (anda bisa memilih lebih dari satu opsi):\n"
        f"Pilihan anda saat ini: {', '.join(user_data[f'{current_step}_selected']) if user_data[f'{current_step}_selected'] else 'Belum ada'}", 
        reply_markup=reply_markup
    )

# OCR Functions
def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file using OCR if needed"""
    # First try to extract text directly if it's a searchable PDF
    try:
        reader = PyPDF2.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
        
        # If we got meaningful text, return it
        if len(text.strip()) > 100:  # Assume if we got >100 chars, it's real text
            return text
    except Exception as e:
        print(f"Error extracting text directly from PDF: {e}")
    
    # If direct extraction failed or returned minimal text, use OCR
    try:
        # Create a temporary directory for images
        with tempfile.TemporaryDirectory() as path:
            # Convert PDF to images
            images = convert_from_path(pdf_path, output_folder=path)
            
            # Extract text from each image
            text = ""
            for image in images:
                text += image_to_string(image, lang='ind')
            
            return text
    except Exception as e:
        print(f"Error during PDF OCR processing: {e}")
        return ""

def extract_text_from_image(image_path):
    """Extract text from image file using OCR"""
    try:
        image = Image.open(image_path)
        text = image_to_string(image, lang='ind')
        return text
    except Exception as e:
        print(f"Error during image OCR processing: {e}")
        return ""

async def verify_document_with_ocr(file_path, document_type):
    """
    Verify if the uploaded document matches the expected document type using OCR.
    
    Args:
        file_path (str): Path to the uploaded file
        document_type (str): Type of document expected ("Surat_Tugas" or "Surat_Permohonan")
        
    Returns:
        tuple: (is_valid, message) - Boolean indicating if document is valid and a message
    """
    # Check if the document type is supported
    if document_type not in REQUIRED_KEYWORDS:
        return False, f"Tipe dokumen {document_type} tidak didukung untuk verifikasi OCR."
    
    try:
        # Get file extension
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Extract text based on file type
        if file_extension == '.pdf':
            text = extract_text_from_pdf(file_path)
        elif file_extension in ['.jpg', '.jpeg', '.png']:
            text = extract_text_from_image(file_path)
        else:
            return False, "Format file tidak didukung. Gunakan PDF, JPG, atau PNG."
        
        # Convert extracted text to lowercase for case-insensitive matching
        text_lower = text.lower()
        
        # Check for required keywords
        keywords = REQUIRED_KEYWORDS[document_type]
        matches = []
        
        for keyword in keywords:
            if keyword in text_lower:
                matches.append(keyword)
        
        # Calculate match percentage
        match_percentage = (len(matches) / len(keywords)) * 100
        
        # Verify if document meets minimum criteria
        if len(matches) >= MIN_KEYWORD_MATCHES:
            return True, f"Dokumen {document_type.replace('_', ' ')} valid dengan tingkat kesesuaian {match_percentage:.1f}%."
        else:
            missing_keywords = [k for k in keywords if k not in matches]
            return False, f"Dokumen tidak memenuhi kriteria {document_type.replace('_', ' ')}. " \
                         f"Kata kunci yang tidak ditemukan: {', '.join(missing_keywords)}."
                         
    except Exception as e:
        return False, f"Gagal memverifikasi dokumen: {str(e)}"

# Fungsi untuk menangani pesan dari pengguna
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text
    user_data = context.user_data

    # Menangani pemilihan layanan
    if 'selected_service' not in user_data:
        if text in LAYANAN_STEPS:
            user_data['selected_service'] = text
            user_data['step_index'] = 0
            current_step = LAYANAN_STEPS[text][0]
            
            if is_file_step(text, current_step):
                await update.message.reply_text(f"Silakan unggah file {current_step.replace('_', ' ')} dalam format PDF, JPG, atau PNG.")
            elif is_multiple_choice_step(text, current_step):
                await show_multiple_choice_options(update, context)
            elif is_terms_step(current_step):
                await show_terms_and_conditions(update, context)
            else:
                await update.message.reply_text(f"Silakan masukkan {current_step.replace('_', ' ')}")
        else:
            await update.message.reply_text("Silakan pilih layanan yang tersedia dari menu.")
        return

    selected_service = user_data['selected_service']
    step_index = user_data['step_index']
    steps = LAYANAN_STEPS[selected_service]
    current_step = steps[step_index]

    # Jika langkah ini membutuhkan file, arahkan pengguna untuk mengunggah file
    if is_file_step(selected_service, current_step):
        await update.message.reply_text(f"Silakan unggah file {current_step.replace('_', ' ')} dalam format PDF, JPG, atau PNG.")
        return
    
    # Handle multiple choice selection
    if is_multiple_choice_step(selected_service, current_step):
        if text == "✓ Selesai Memilih":
            # Pengguna selesai memilih, gabungkan semua pilihan menjadi string
            if f"{current_step}_selected" in user_data and user_data[f"{current_step}_selected"]:
                user_data[current_step] = ", ".join(sorted(user_data[f"{current_step}_selected"]))
                # Pindah ke langkah berikutnya
                await move_to_next_step(update, context)
            else:
                await update.message.reply_text("Anda harus memilih minimal satu opsi.")
            return
        
        # Proses pilihan multiple choice
        choices = MULTIPLE_CHOICE_STEPS[selected_service][current_step]
        for choice in choices:
            if text == f"⬜ {choice}":
                # Tambahkan pilihan ke set
                user_data[f"{current_step}_selected"].add(choice)
                await show_multiple_choice_options(update, context)
                return
            elif text == f"✅ {choice}":
                # Hapus pilihan dari set
                user_data[f"{current_step}_selected"].discard(choice)
                await show_multiple_choice_options(update, context)
                return
        
        # Jika input tidak valid untuk multiple choice
        await update.message.reply_text("Silakan pilih dari opsi yang tersedia.")
        await show_multiple_choice_options(update, context)
        return

    # Validasi input berdasarkan regex
    is_valid, error_message = validate_input(text, current_step)
    if not is_valid:
        await update.message.reply_text(error_message)
        return

    # Simpan input pengguna
    user_data[current_step] = text

    # Pindah ke langkah berikutnya
    await move_to_next_step(update, context)

# Fungsi untuk menampilkan syarat dan ketentuan
async def show_terms_and_conditions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    service = user_data['selected_service']
    
    if service in SYARAT_DAN_KETENTUAN:
        terms_text = SYARAT_DAN_KETENTUAN[service]
        
        # Buat inline keyboard untuk setuju/tidak setuju
        keyboard = [
            [InlineKeyboardButton("Setuju", callback_data="terms_agree")],
            [InlineKeyboardButton("Tidak Setuju", callback_data="terms_disagree")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(terms_text, reply_markup=reply_markup)
    else:
        # Jika tidak ada syarat dan ketentuan yang didefinisikan, lanjut ke langkah berikutnya
        await move_to_next_step(update, context)

# Fungsi untuk menangani callback dari tombol inline
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_data = context.user_data
    selected_service = user_data.get('selected_service')
    step_index = user_data.get('step_index')
    
    if not selected_service or step_index is None:
        await query.message.reply_text("Sesi Anda telah kedaluwarsa. Silakan mulai ulang dengan /start")
        return
    
    steps = LAYANAN_STEPS[selected_service]
    current_step = steps[step_index]
    
    if query.data == "terms_agree":
        user_data[current_step] = "Setuju"
        await query.message.reply_text("✅ Anda telah menyetujui syarat dan ketentuan.")
        await move_to_next_step(update, context)
    elif query.data == "terms_disagree":
        await query.message.reply_text("❌ Permintaan dibatalkan karena Anda tidak menyetujui syarat dan ketentuan.", 
                                     reply_markup=ReplyKeyboardRemove())
        user_data.clear()

# Fungsi untuk pindah ke langkah berikutnya
async def move_to_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    selected_service = user_data['selected_service']
    step_index = user_data['step_index']
    steps = LAYANAN_STEPS[selected_service]

    # Jika masih ada langkah selanjutnya, lanjutkan ke langkah berikutnya
    if step_index + 1 < len(steps):
        user_data['step_index'] += 1
        next_step = steps[user_data['step_index']]
        
        if is_file_step(selected_service, next_step):
            await update.message.reply_text(f"Silakan unggah file {next_step.replace('_', ' ')} dalam format PDF, JPG, atau PNG.")
        elif is_multiple_choice_step(selected_service, next_step):
            # Inisialisasi set untuk pilihan
            user_data[f"{next_step}_selected"] = set()
            if hasattr(update, 'message') and update.message:
                await show_multiple_choice_options(update, context)
            else:
                # Handle jika dipanggil dari callback
                await update.callback_query.message.reply_text("Menampilkan pilihan...")
                update_adapter = UpdateAdapter(update.callback_query.message)
                await show_multiple_choice_options(update_adapter, context)
        elif is_terms_step(next_step):
            if hasattr(update, 'message') and update.message:
                await show_terms_and_conditions(update, context)
            else:
                # Jika ini dipanggil dari callback query
                await update.callback_query.message.reply_text("Menampilkan syarat dan ketentuan...")
                await show_terms_and_conditions(UpdateAdapter(update.callback_query.message), context)
        else:
            # Gunakan update.message jika ada, atau callback_query.message jika update adalah callback
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(f"Silakan masukkan {next_step.replace('_', ' ')}:")
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(f"Silakan masukkan {next_step.replace('_', ' ')}:")
    else:
        # Semua langkah selesai, simpan ke Google Sheets
        if save_to_google_sheets(user_data, selected_service):
            message_obj = update.message if hasattr(update, 'message') and update.message else update.callback_query.message
            await message_obj.reply_text("✅ Data berhasil disimpan ke Google Sheets.")
        else:
            message_obj = update.message if hasattr(update, 'message') and update.message else update.callback_query.message
            await message_obj.reply_text("❌ Gagal menyimpan data ke Google Sheets.")

        # Tampilkan ringkasan data yang dimasukkan
        response = f"Terima kasih, berikut data Anda untuk {selected_service}:\n" + '\n'.join(
            [f"{key.replace('_', ' ')}: {user_data.get(key, '')}" for key in steps]
        )
        
        message_obj = update.message if hasattr(update, 'message') and update.message else update.callback_query.message
        await message_obj.reply_text(response, reply_markup=ReplyKeyboardRemove())
        user_data.clear()

# Kelas bantuan untuk membuat objek yang kompatibel dengan update.message
class UpdateAdapter:
    def __init__(self, message):
        self.message = message

# Handle file dengan OCR verification
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data

    # Pastikan pengguna sudah memilih layanan
    if 'selected_service' not in user_data:
        await update.message.reply_text("Silakan pilih layanan terlebih dahulu dengan mengetik /start")
        return

    selected_service = user_data['selected_service']
    step_index = user_data.get('step_index', 0)
    steps = LAYANAN_STEPS[selected_service]
    
    if step_index >= len(steps):
        await update.message.reply_text("Semua langkah sudah selesai. Ketik /start untuk memulai lagi.")
        return
    
    current_step = steps[step_index]
    
    # Cek apakah langkah saat ini memerlukan file
    if not is_file_step(selected_service, current_step):
        await update.message.reply_text(f"Langkah ini tidak memerlukan file. Silakan masukkan {current_step.replace('_', ' ')}.")
        return

    # Validasi file yang diunggah
    file = update.message.document
    if not file:
        await update.message.reply_text("Harap kirimkan file yang sesuai.")
        return
    
    file_extension = file.file_name.split(".")[-1].lower()
    if file_extension not in ["pdf", "jpg", "png"]:
        await update.message.reply_text("Format file tidak didukung. Gunakan PDF, JPG, atau PNG.")
        return

    # Buat nama file yang unik berdasarkan timestamp untuk menghindari konflik
    import time
    timestamp = int(time.time())
    file_path = f"temp_{timestamp}_{file.file_name}"
    file_info = await file.get_file()
    
    try:
        # Download file dari Telegram
        await file_info.download_to_drive(file_path)
        
        # Verifikasi dokumen dengan OCR
        await update.message.reply_text(f"Memverifikasi dokumen {current_step.replace('_', ' ')}... Mohon tunggu sebentar.")
        is_valid, verification_message = await verify_document_with_ocr(file_path, current_step)
        
        if not is_valid:
            await update.message.reply_text(f"❌ {verification_message}\nSilakan unggah dokumen yang sesuai.")
            delete_temp_file(file_path)
            return
            
        # Upload ke Google Drive
        file_metadata = {"name": file.file_name, "parents": [FOLDER_ID]}