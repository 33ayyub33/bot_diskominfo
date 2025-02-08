import asyncio
from typing import Final
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials
import os
import gspread
from google.oauth2.service_account import Credentials
#from googleapiclient.discovery import build
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# Token dan Username Bot
TOKEN: Final = '8116521602:AAFKMElIZp8RluE_4eqVchrdQZTCq-O_zUk'
BOT_USERNAME: Final = '@kominfoo_bot'

    # Load kredensial JSON untuk Google Sheets API
SERVICE_ACCOUNT_FILE = "credentials.json"  # Ganti dengan path file JSON yang diunduh
SPREADSHEET_ID = "1wdpE2wgn-OnFZ75LT3agsPCjzIjAVONXs-as63xGivo"  # Ganti dengan ID Google Spreadsheet

# Konfigurasi Google Drive dan Sheets
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
SERVICE_ACCOUNT_FILE = "credentials.json"
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build("drive", "v3", credentials=creds)

# Autentikasi ke Google Sheets
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # Akses ke sheet pertama

# Fungsi untuk menyimpan data ke Google Sheets
def save_to_google_sheets(user_data):
    try:
        row = [user_data.get(key, "") for key in user_data.keys()]
        sheet.append_row(row)  # Tambahkan data ke baris baru
        return True
    except Exception as e:
        print(f"Error saat menyimpan ke Google Sheets: {e}")
        return False
    
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = f"temp_{update.message.document.file_name}"
    await file.download(file_path)

    # Upload ke Google Drive
    file_metadata = {"name": update.message.document.file_name, "parents": ["YOUR_DRIVE_FOLDER_ID"]}
    media = MediaFileUpload(file_path, mimetype=update.message.document.mime_type)
    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_link = f"https://drive.google.com/file/d/{uploaded_file['id']}/view?usp=sharing"

    # Hapus file lokal
    os.remove(file_path)

    await update.message.reply_text(f"File berhasil diunggah! Link: {file_link}")
    return file_link

# Mapping layanan ke langkah-langkah yang diperlukan
LAYANAN_STEPS = {
    "Pengajuan tanda Tangan Elektronik": ["Nama_Lengkap", "NIP_ASN", "NIK_KTP", "Nama_OPD", "Nomor_Handphone", "Alamat_Email", "Jabatan"],
    "Pembuatan Email Dinas": ["Nama_OPD", "Nama_PIC", "Nomor_Handphone", "Permohonan_Pembuatan_Email", "Pengajuan_Pembuatan_Email", "Syarat_dan_Ketentuan"],
    "Reset password Email Dinas": ["Nama_Lengkap", "NIP_Pemohon", "Nomor_Handphone", "Nama_User", "NIK_User", "NIP_User", "Alamat_Email", "Tindakan", "Alasan", "Syarat_dan_Ketentuan"],
    "Reset Passphrase TTE/Perpanjangan TTE": ["Nama_Lengkap", "NIP_Pemohon", "Nomor_Handphone", "Nama_User", "NIK_User", "NIP_User", "Alamat_Email", "Tindakan", "Alasan", "Syarat_dan_Ketentuan"],
    "Reset/Permintaan Akun Cpanel": ["Nama_Lengkap", "NIP_Pemohon", "Jabatan", "Asal_OPD", "URL_Aplikasi", "Surat Tugas Pengambilan Berita Acara", "Syarat_dan_Ketentuan"],
    "Permohonan video conference": ["Nama_Lengkap", "NIP_Pemohon", "Nomor_Handphone", "Unit_Kerja", "Nama_Acara", "Tempat", "Tanggal_Mulai", "Tanggal_Selesai", "Waktu", "Estimasi_Jumlah_Partisipan", "Live_Youtube", "Permohonan_Bantuan", "Email_Dinas", "Informasi_Tambahan", "Surat_Permohonan"],
}

# Opsi untuk Tindakan dan Syarat_dan_Ketentuan
TINDAKAN_OPTIONS = ["Reset Password", "Hapus Akun"]
SYARAT_OPTIONS = ["Setuju", "Tidak Setuju"]

# Fungsi untuk menangani perintah /start
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[service] for service in LAYANAN_STEPS.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Silakan pilih salah satu layanan berikut:', reply_markup=reply_markup)

# Fungsi menangani input pengguna secara dinamis
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    text = update.message.text
    user_data = context.user_data

    # Jika belum ada layanan yang dipilih, pilih layanan
    if 'selected_service' not in user_data:
        if text in LAYANAN_STEPS:
            user_data['selected_service'] = text
            user_data['step_index'] = 0  # Mulai dari langkah pertama
            await update.message.reply_text(f"Silakan masukkan {LAYANAN_STEPS[text][0]}:")
        else:
            await update.message.reply_text("Silakan pilih layanan yang tersedia dari menu.")
        return

    # Ambil layanan yang dipilih dan langkah saat ini
    selected_service = user_data['selected_service']
    step_index = user_data['step_index']
    steps = LAYANAN_STEPS[selected_service]

    # Cek apakah langkah ini adalah "Tindakan"
    if steps[step_index] == "Tindakan":
        if text not in TINDAKAN_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in TINDAKAN_OPTIONS]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Silakan pilih salah satu tindakan:", reply_markup=reply_markup)
            return

    # Cek apakah langkah ini adalah "Syarat_dan_Ketentuan"
    if steps[step_index] == "Syarat_dan_Ketentuan":
        if text not in SYARAT_OPTIONS:
            keyboard = [[KeyboardButton(opt)] for opt in SYARAT_OPTIONS]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Apakah Anda setuju dengan syarat dan ketentuan?", reply_markup=reply_markup)
            return
        elif text == "Tidak Setuju":
            await update.message.reply_text("Permintaan dibatalkan karena Anda tidak setuju dengan syarat dan ketentuan.")
            user_data.clear()
            return

    # Simpan input pengguna ke dalam user_data
    user_data[steps[step_index]] = text

    # Cek apakah masih ada langkah berikutnya
    if step_index + 1 < len(steps):
        user_data['step_index'] += 1
        next_step = steps[user_data['step_index']]

        # Jika langkah berikutnya adalah "Tindakan", tampilkan pilihan
        if next_step == "Tindakan":
            keyboard = [[KeyboardButton(opt)] for opt in TINDAKAN_OPTIONS]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Silakan pilih salah satu tindakan:", reply_markup=reply_markup)
        # Jika langkah berikutnya adalah "Syarat_dan_Ketentuan", tampilkan konfirmasi
        elif next_step == "Syarat_dan_Ketentuan":
            keyboard = [[KeyboardButton(opt)] for opt in SYARAT_OPTIONS]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Apakah Anda setuju dengan syarat dan ketentuan?", reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"Silakan masukkan {next_step}:")
    else:
        if save_to_google_sheets(user_data):
            await update.message.reply_text("Data berhasil disimpan ke Google Sheets ✅")
        else:
            await update.message.reply_text("Gagal menyimpan data ke Google Sheets ❌")
        
        response = f"Terima kasih, berikut data yang Anda masukkan untuk {selected_service}:\n"
        response += '\n'.join([f"{key}: {user_data[key]}" for key in steps])
        await update.message.reply_text(response)
        
        user_data.clear() 




# Fungsi utama
if __name__ == '__main__':
    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()

    # Menambahkan handler
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print('Polling...')
    app.run_polling(poll_interval=3)