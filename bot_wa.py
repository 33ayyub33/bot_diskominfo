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
from telegram.ext import CallbackContext
import datetime
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN: Final = '8116521602:AAFKMElIZp8RluE_4eqVchrdQZTCq-O_zUk'
BOT_USERNAME: Final = '@kominfoo_bot'

# Konfigurasi Google Drive dan Sheets
SERVICE_ACCOUNT_FILE = "credentials.json"
SPREADSHEET_ID = "1wdpE2wgn-OnFZ75LT3agsPCjzIjAVONXs-as63xGivo"
FOLDER_ID = "13XaW0qsyE6Cwcd6szdhbGfk4h32bgRnL"

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Admin User IDs - Daftar user ID Telegram admin
ADMIN_IDS = [5546940331, 87654321]  # Ganti dengan ID admin yang sebenarnya

#5546940331

# Folder ID untuk setiap layanan
SERVICE_FOLDERS = {
    "Pengajuan Tanda Tangan Elektronik": "1RDU-wWsSrcgD65w8v-0d0vK7Ea6zVkkC",  # Ganti dengan ID folder yang sesuai
    "Reset/Permintaan Akun Cpanel": "1tBQUlOTo4e_I5fJ3_KvZBQlL60LqkEpE",    # Ganti dengan ID folder yang sesuai
    "Permohonan Video Conference": "17HxA3Mb2RqHbsfOlligsr-2DyPJNdsnc"      # Ganti dengan ID folder yang sesuai
}

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



# Status options for submissions
STATUS_OPTIONS = ["Diproses", "Disetujui", "Ditolak"]
DEFAULT_STATUS = "Diproses"

# Dictionary to store user submission mappings
USER_SUBMISSION_MAP = {}

# Admin command handler
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Anda tidak memiliki akses ke panel admin.")
        return
    
    # Show admin panel with options
    keyboard = [
        ["🔎 Lihat Semua Laporan"],
        ["🔍 Filter Laporan"],
        ["📊 Statistik Laporan"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Panel Admin", reply_markup=reply_markup)

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        return False  # Not an admin
    
    # Admin panel navigation
    if text == "🔎 Lihat Semua Laporan":
        await show_services_selection(update, context)
        return True
    elif text == "🔍 Filter Laporan":
        keyboard = [
            ["📅 Filter berdasar Tanggal"],
            ["👤 Filter berdasar NIP"],
            ["📋 Filter berdasar Status"],
            ["🔙 Kembali ke Panel Admin"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Pilih metode filter:", reply_markup=reply_markup)
        return True
    elif text == "📊 Statistik Laporan":
        await show_stats(update, context)
        return True
    elif text == "🔙 Kembali ke Panel Admin":
        await admin_command(update, context)
        return True
    elif text.startswith("📅 Filter berdasar Tanggal"):
        context.user_data['admin_filter_mode'] = 'date'
        await update.message.reply_text("Masukkan rentang tanggal (format: DD/MM/YYYY - DD/MM/YYYY):")
        return True
    elif text.startswith("👤 Filter berdasar NIP"):
        context.user_data['admin_filter_mode'] = 'nip'
        await update.message.reply_text("Masukkan NIP:")
        return True
    elif text.startswith("📋 Filter berdasar Status"):
        context.user_data['admin_filter_mode'] = 'status'
        keyboard = [[status] for status in STATUS_OPTIONS]
        keyboard.append(["🔙 Kembali"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Pilih status:", reply_markup=reply_markup)
        return True
    
    # Handle filter inputs
    if 'admin_filter_mode' in context.user_data:
        filter_mode = context.user_data['admin_filter_mode']
        
        if filter_mode == 'date' and re.match(r'^\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}$', text):
            # Process date range filter
            dates = text.split('-')
            start_date = dates[0].strip()
            end_date = dates[1].strip()
            await filter_submissions_by_date(update, context, start_date, end_date)
            return True
        elif filter_mode == 'nip' and re.match(r'^\d{18}$', text):
            # Process NIP filter
            await filter_submissions_by_nip(update, context, text)
            return True
        elif filter_mode == 'status' and text in STATUS_OPTIONS:
            # Process status filter
            await filter_submissions_by_status(update, context, text)
            return True
    
    # Handle service selection
    if text in LAYANAN_STEPS.keys():
        context.user_data['selected_admin_service'] = text
        await show_service_submissions(update, context, text)
        return True
    
    # Check if this is a submission ID selection for status update
    if 'admin_viewing_submissions' in context.user_data and text.isdigit():
        submission_index = int(text) - 1
        if submission_index >= 0 and submission_index < len(context.user_data['admin_viewing_submissions']):
            await show_submission_status_options(update, context, submission_index)
            return True
    
    # Check if this is a status update selection
    if 'admin_editing_submission' in context.user_data and text in STATUS_OPTIONS:
        await update_submission_status(update, context, text)
        return True
    
    return False  # Message not handled by admin functions

async def show_submission_status_options(update: Update, context: ContextTypes.DEFAULT_TYPE, submission_index):
    submissions = context.user_data['admin_viewing_submissions']
    submission = submissions[submission_index]
    
    context.user_data['admin_editing_submission'] = {
        'service': submission['service'],
        'row_index': submission['row_index'],
        'data': submission
    }
    
    keyboard = [[status] for status in STATUS_OPTIONS]
    keyboard.append(["🔙 Kembali"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    message = f"Submission #{submission_index + 1}\n"
    message += f"Layanan: {submission['service']}\n"
    message += f"Nama: {submission['data'].get('Nama_Lengkap', 'N/A')}\n"
    message += f"NIP: {submission['data'].get('NIP_ASN', submission['data'].get('NIP_Pemohon', 'N/A'))}\n"
    message += f"Status Saat Ini: {submission['status']}\n\n"
    message += "Pilih status baru:"
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def update_submission_status(update: Update, context: ContextTypes.DEFAULT_TYPE, new_status):
    submission_info = context.user_data['admin_editing_submission']
    service = submission_info['service']
    row_index = submission_info['row_index']
    old_status = submission_info['data']['status']
    user_id = submission_info['data'].get('user_id', None)
    
    if new_status == old_status:
        await update.message.reply_text(f"Status tidak berubah: {new_status}")
        return
    
    try:
        # Get the worksheet
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service)
        
        # Get the status column index (we added status at the end of the service fields + 1 for user_id)
        status_col_index = len(LAYANAN_STEPS[service]) + 1
        
        # Update the status in the worksheet
        worksheet.update_cell(row_index, status_col_index, new_status)
        
        await update.message.reply_text(f"✅ Status berhasil diubah dari '{old_status}' menjadi '{new_status}'")
        
        # Notify the user about status change
        if user_id:
            try:
                nama = submission_info['data'].get('Nama_Lengkap', 'N/A')
                nip = submission_info['data'].get('NIP_ASN', submission_info['data'].get('NIP_Pemohon', 'N/A'))
                
                notification_message = f"🔔 PERUBAHAN STATUS PENGAJUAN\n\n" \
                                     f"Layanan: {service}\n" \
                                     f"Nama: {nama}\n" \
                                     f"NIP: {nip}\n" \
                                     f"Status: {old_status} ➡️ {new_status}\n\n"
                
                if new_status == "Disetujui":
                    notification_message += "Pengajuan Anda telah disetujui. Terima kasih."
                elif new_status == "Ditolak":
                    notification_message += "Mohon maaf, pengajuan Anda ditolak. Silakan hubungi admin untuk informasi lebih lanjut."
                
                await context.bot.send_message(
                    chat_id=int(user_id),
                    text=notification_message,
                    parse_mode="Markdown"
                )
                
                # Also update in our local map
                if int(user_id) in USER_SUBMISSION_MAP:
                    USER_SUBMISSION_MAP[int(user_id)]['status'] = new_status
                
                logger.info(f"Status notification sent to user {user_id}")
            except Exception as e:
                logger.error(f"Error sending status notification to user {user_id}: {str(e)}")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal mengubah status: {str(e)}")
    
    # Clear the editing context
    if 'admin_editing_submission' in context.user_data:
        del context.user_data['admin_editing_submission']
    
    # Return to the submission list
    await show_service_submissions(update, context, service)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = {}
    total_submissions = 0
    
    try:
        for service in LAYANAN_STEPS.keys():
            try:
                worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service)
                values = worksheet.get_all_values()
                
                if len(values) <= 1:  # Only header row or empty
                    stats[service] = {"total": 0, "status": {}}
                    continue
                
                # Skip header row
                data_rows = values[1:]
                total_for_service = len(data_rows)
                total_submissions += total_for_service
                
                # Status count (status is in the column after all service fields)
                status_col_idx = len(LAYANAN_STEPS[service])
                status_counts = {}
                
                for row in data_rows:
                    if len(row) > status_col_idx:
                        status = row[status_col_idx]
                        if status in status_counts:
                            status_counts[status] += 1
                        else:
                            status_counts[status] = 1
                
                stats[service] = {
                    "total": total_for_service,
                    "status": status_counts
                }
            except gspread.exceptions.WorksheetNotFound:
                stats[service] = {"total": 0, "status": {}}
    
        # Build stats message
        message = "📊 STATISTIK LAPORAN\n\n"
        message += f"Total Pengajuan: {total_submissions}\n\n"
        
        for service, service_stats in stats.items():
            message += f"{service}\n"
            message += f"Total: {service_stats['total']}\n"
            
            for status, count in service_stats['status'].items():
                message += f"- {status}: {count}\n"
            
            message += "\n"
        
        await update.message.reply_text(message, parse_mode="Markdown")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal mendapatkan statistik: {str(e)}")

async def show_services_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[service] for service in LAYANAN_STEPS.keys()]
    keyboard.append(["🔙 Kembali ke Panel Admin"])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Pilih layanan:", reply_markup=reply_markup)

async def show_service_submissions(update: Update, context: ContextTypes.DEFAULT_TYPE, service):
    try:
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service)
        values = worksheet.get_all_values()
        
        if len(values) <= 1:  # Only header or empty
            await update.message.reply_text(f"Tidak ada pengajuan untuk layanan {service}.")
            return
        
        # Get the headers and data
        headers = values[0]
        data_rows = values[1:]
        
        # Status column index
        status_col_idx = len(LAYANAN_STEPS[service])
        user_id_col_idx = status_col_idx + 1  # user_id column is right after status
        timestamp_col_idx = user_id_col_idx + 1  # timestamp is after user_id
        
        # Prepare submission list
        submissions = []
        for i, row in enumerate(data_rows, start=2):  # i starts from 2 for sheet row index (1-based and header is row 1)
            submission = {}
            for j, header in enumerate(LAYANAN_STEPS[service]):
                if j < len(row):
                    submission[header] = row[j]
            
            # Add status, user_id, and timestamp if available
            status = row[status_col_idx] if len(row) > status_col_idx else DEFAULT_STATUS
            user_id = row[user_id_col_idx] if len(row) > user_id_col_idx else None
            timestamp = row[timestamp_col_idx] if len(row) > timestamp_col_idx else "N/A"
            
            submissions.append({
                "service": service,
                "row_index": i,  # Actual row index in the sheet (1-based)
                "data": submission,
                "status": status,
                "user_id": user_id,
                "timestamp": timestamp
            })
        
        # Store submissions for later reference
        context.user_data['admin_viewing_submissions'] = submissions
        
        # Create the message
        if submissions:
            message = f"DAFTAR PENGAJUAN {service}\n\n"
            
            for i, submission in enumerate(submissions, start=1):
                nama = submission['data'].get('Nama_Lengkap', 'N/A')
                nip = submission['data'].get('NIP_ASN', submission['data'].get('NIP_Pemohon', 'N/A'))
                status = submission['status']
                timestamp = submission['timestamp']
                
                message += f"{i}. {nama} ({nip})\n"
                message += f"   Status: {status}\n"
                message += f"   Waktu: {timestamp}\n\n"
                
                # If message becomes too long, send it and start a new one
                if len(message) > 3500:
                    await update.message.reply_text(message, parse_mode="Markdown")
                    message = "(Lanjutan...)\n\n"
            
            message += "Pilih nomor pengajuan untuk mengelola status."
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Tidak ada pengajuan untuk layanan {service}.")
    
    except gspread.exceptions.WorksheetNotFound:
        await update.message.reply_text(f"Belum ada pengajuan untuk layanan {service}.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


async def filter_submissions_by_date(update: Update, context: ContextTypes.DEFAULT_TYPE, start_date, end_date):
    try:
        from datetime import datetime
        
        # Parse dates to datetime objects
        start_dt = datetime.strptime(start_date, "%d/%m/%Y")
        end_dt = datetime.strptime(end_date, "%d/%m/%Y")
        
        all_filtered_submissions = []
        
        for service in LAYANAN_STEPS.keys():
            try:
                worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service)
                values = worksheet.get_all_values()
                
                if len(values) <= 1:
                    continue
                
                headers = values[0]
                data_rows = values[1:]
                
                # Status and timestamp column indexes
                status_col_idx = len(LAYANAN_STEPS[service])
                user_id_col_idx = status_col_idx + 1
                timestamp_col_idx = user_id_col_idx + 1
                
                for i, row in enumerate(data_rows, start=2):
                    if len(row) <= timestamp_col_idx:
                        continue
                    
                    timestamp_str = row[timestamp_col_idx]
                    try:
                        # Parse the timestamp - adjust format if needed
                        submission_dt = datetime.strptime(timestamp_str.split(" ")[0], "%d/%m/%Y")
                        
                        # Check if the date is in range
                        if start_dt <= submission_dt <= end_dt:
                            submission = {}
                            for j, header in enumerate(LAYANAN_STEPS[service]):
                                if j < len(row):
                                    submission[header] = row[j]
                            
                            status = row[status_col_idx] if len(row) > status_col_idx else DEFAULT_STATUS
                            user_id = row[user_id_col_idx] if len(row) > user_id_col_idx else None
                            
                            all_filtered_submissions.append({
                                "service": service,
                                "row_index": i,
                                "data": submission,
                                "status": status,
                                "user_id": user_id,
                                "timestamp": timestamp_str
                            })
                    except Exception as e:
                        logger.error(f"Error parsing date {timestamp_str}: {str(e)}")
            
            except gspread.exceptions.WorksheetNotFound:
                continue
        
        # Store and display filtered submissions
        context.user_data['admin_viewing_submissions'] = all_filtered_submissions
        
        if all_filtered_submissions:
            message = f"HASIL FILTER TANGGAL {start_date} - {end_date}\n\n"
            
            for i, submission in enumerate(all_filtered_submissions, start=1):
                service = submission['service']
                nama = submission['data'].get('Nama_Lengkap', 'N/A')
                nip = submission['data'].get('NIP_ASN', submission['data'].get('NIP_Pemohon', 'N/A'))
                status = submission['status']
                timestamp = submission['timestamp']
                
                message += f"{i}. {service}\n"
                message += f"   Nama: {nama} ({nip})\n"
                message += f"   Status: {status}\n"
                message += f"   Waktu: {timestamp}\n\n"
                
                if len(message) > 3500:
                    await update.message.reply_text(message, parse_mode="Markdown")
                    message = "(Lanjutan...)\n\n"
            
            message += "Pilih nomor pengajuan untuk mengelola status."
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Tidak ada pengajuan dalam rentang tanggal {start_date} - {end_date}.")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error saat melakukan filter: {str(e)}")

async def filter_submissions_by_nip(update: Update, context: ContextTypes.DEFAULT_TYPE, nip):
    try:
        all_filtered_submissions = []
        
        for service in LAYANAN_STEPS.keys():
            try:
                worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service)
                values = worksheet.get_all_values()
                
                if len(values) <= 1:
                    continue
                
                headers = values[0]
                data_rows = values[1:]
                
                # Find NIP columns (could be NIP_ASN or NIP_Pemohon)
                nip_col_indexes = []
                for idx, header in enumerate(headers):
                    if header in ["NIP_ASN", "NIP_Pemohon"]:
                        nip_col_indexes.append(idx)
                
                if not nip_col_indexes:
                    continue
                
                # Status column indexes
                status_col_idx = len(LAYANAN_STEPS[service])
                user_id_col_idx = status_col_idx + 1
                timestamp_col_idx = user_id_col_idx + 1
                
                for i, row in enumerate(data_rows, start=2):
                    for nip_idx in nip_col_indexes:
                        if nip_idx < len(row) and row[nip_idx] == nip:
                            submission = {}
                            for j, header in enumerate(LAYANAN_STEPS[service]):
                                if j < len(row):
                                    submission[header] = row[j]
                            
                            status = row[status_col_idx] if len(row) > status_col_idx else DEFAULT_STATUS
                            user_id = row[user_id_col_idx] if len(row) > user_id_col_idx else None
                            timestamp = row[timestamp_col_idx] if len(row) > timestamp_col_idx else "N/A"
                            
                            all_filtered_submissions.append({
                                "service": service,
                                "row_index": i,
                                "data": submission,
                                "status": status,
                                "user_id": user_id,
                                "timestamp": timestamp
                            })
                            break
            
            except gspread.exceptions.WorksheetNotFound:
                continue
        
        # Store and display filtered submissions
        context.user_data['admin_viewing_submissions'] = all_filtered_submissions
        
        if all_filtered_submissions:
            message = f"HASIL FILTER NIP: {nip}\n\n"
            
            for i, submission in enumerate(all_filtered_submissions, start=1):
                service = submission['service']
                nama = submission['data'].get('Nama_Lengkap', 'N/A')
                status = submission['status']
                timestamp = submission['timestamp']
                
                message += f"{i}. {service}\n"
                message += f"   Nama: {nama}\n"
                message += f"   Status: {status}\n"
                message += f"   Waktu: {timestamp}\n\n"
            
            message += "Pilih nomor pengajuan untuk mengelola status."
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Tidak ada pengajuan dengan NIP {nip}.")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error saat melakukan filter: {str(e)}")

async def filter_submissions_by_status(update: Update, context: ContextTypes.DEFAULT_TYPE, status):
    try:
        all_filtered_submissions = []
        
        for service in LAYANAN_STEPS.keys():
            try:
                worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service)
                values = worksheet.get_all_values()
                
                if len(values) <= 1:
                    continue
                
                headers = values[0]
                data_rows = values[1:]
                
                # Status column index
                status_col_idx = len(LAYANAN_STEPS[service])
                user_id_col_idx = status_col_idx + 1
                timestamp_col_idx = user_id_col_idx + 1
                
                for i, row in enumerate(data_rows, start=2):
                    if len(row) > status_col_idx and row[status_col_idx] == status:
                        submission = {}
                        for j, header in enumerate(LAYANAN_STEPS[service]):
                            if j < len(row):
                                submission[header] = row[j]
                        
                        user_id = row[user_id_col_idx] if len(row) > user_id_col_idx else None
                        timestamp = row[timestamp_col_idx] if len(row) > timestamp_col_idx else "N/A"
                        
                        all_filtered_submissions.append({
                            "service": service,
                            "row_index": i,
                            "data": submission,
                            "status": status,
                            "user_id": user_id,
                            "timestamp": timestamp
                        })
            
            except gspread.exceptions.WorksheetNotFound:
                continue
        
        # Store and display filtered submissions
        context.user_data['admin_viewing_submissions'] = all_filtered_submissions
        
        if all_filtered_submissions:
            message = f"HASIL FILTER STATUS: {status}\n\n"
            
            for i, submission in enumerate(all_filtered_submissions, start=1):
                service = submission['service']
                nama = submission['data'].get('Nama_Lengkap', 'N/A')
                nip = submission['data'].get('NIP_ASN', submission['data'].get('NIP_Pemohon', 'N/A'))
                timestamp = submission['timestamp']
                
                message += f"{i}. {service}\n"
                message += f"   Nama: {nama} ({nip})\n"
                message += f"   Waktu: {timestamp}\n\n"
                
                if len(message) > 3500:
                    await update.message.reply_text(message, parse_mode="Markdown")
                    message = "(Lanjutan...)\n\n"
            
            message += "Pilih nomor pengajuan untuk mengelola status."
            await update.message.reply_text(message, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"Tidak ada pengajuan dengan status {status}.")
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error saat melakukan filter: {str(e)}")





# Mapping layanan dan langkah-langkahnya
LAYANAN_STEPS = {
    "Pengajuan Tanda Tangan Elektronik": ["Nama_Lengkap", "NIP_ASN", "NIK_KTP", "Nama_OPD", "Nomor_Handphone", "Alamat_Email", "Jabatan"],
    "Reset/Permintaan Akun Cpanel": ["Nama_Lengkap", "NIP_Pemohon", "Jabatan", "Asal_OPD", "URL_Aplikasi", "Surat_Tugas", "Syarat_dan_Ketentuan"],
    "Permohonan Video Conference": ["Nama_Lengkap", "NIP_Pemohon", "Nomor_Handphone", "Unit_Kerja", "Nama_Acara", "Tempat", "Tanggal_Mulai", "Tanggal_Selesai", "Waktu", "Estimasi_Jumlah_Partisipan", "Live_Youtube", "Permohonan_Bantuan", "Email_Dinas", "Informasi_Tambahan", "Surat_Permohonan"],
}

# Regex validasi untuk setiap langkah
VALIDASI_REGEX = {
    "Nama_Lengkap": r"^[A-Za-z\s\.]{3,50}$",
    "NIP_ASN": r"^\d{18}$",
    "NIP_Pemohon": r"^\d{18}$",
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

spreadsheet = client.open_by_key(SPREADSHEET_ID)  # Ambil objek Spreadsheet

def save_to_google_sheets(user_data, service_name, user_id=None):
    try:
        # Coba mendapatkan worksheet yang sudah ada
        worksheet = client.open_by_key(SPREADSHEET_ID).worksheet(service_name)
    except gspread.exceptions.WorksheetNotFound:
        # Jika tidak ada, buat worksheet baru
        worksheet = client.open_by_key(SPREADSHEET_ID).add_worksheet(title=service_name, rows="1000", cols="22")  # Added columns for user_id and timestamp
        
        # Add header with Status, User_ID, and Timestamp columns
        header_row = LAYANAN_STEPS[service_name] + ["Status", "User_ID", "Timestamp"]
        worksheet.append_row(header_row)
        
        # Get the status column index
        status_col_index = len(LAYANAN_STEPS[service_name])

        # Set validasi data untuk kolom Status
        request = {
            "setDataValidation": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": status_col_index,
                    "endColumnIndex": status_col_index + 1
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": status} for status in STATUS_OPTIONS]
                    },
                    "showCustomUi": True,
                    "strict": True
                }
            }
        }
        
        # Format header row
        format_request = {
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(header_row)
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.8, "green": 0.8, "blue": 0.8},
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        }

        # Format status column
        status_column_format = {
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": 1,
                    "endRowIndex": 1000,
                    "startColumnIndex": status_col_index,
                    "endColumnIndex": status_col_index + 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(horizontalAlignment)"
            }
        }

        # Apply all formatting
        client.open_by_key(SPREADSHEET_ID).batch_update({
            "requests": [
                request,  # Data validation
                format_request,  # Header formatting
                status_column_format  # Status column formatting
            ]
        })
    
    # Current timestamp
    current_timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Buat row data dengan menambahkan status, user_id, dan timestamp
    row_data = [user_data.get(key, "") for key in LAYANAN_STEPS[service_name]]
    row_data.append(DEFAULT_STATUS)  # Tambahkan status default
    row_data.append(str(user_id) if user_id else "")  # Tambahkan user_id
    row_data.append(current_timestamp)  # Tambahkan timestamp
    
    # Append row ke worksheet
    worksheet.append_row(row_data)
    
    # Jika user_id tersedia, simpan mapping user dengan pengajuan
    if user_id:
        USER_SUBMISSION_MAP[user_id] = {
            'service': service_name,
            'nama': user_data.get('Nama_Lengkap', ''),
            'nip': user_data.get('NIP_ASN', user_data.get('NIP_Pemohon', '')),
            'timestamp': current_timestamp,
            'status': DEFAULT_STATUS
        }
    
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
    
    # Check if user is admin
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        # Redirect to admin panel directly
        await admin_command(update, context)
    else:
        # Regular user flow
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

# Fungsi untuk menangani pesan dari pengguna
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    # Cek apakah pengguna adalah admin
    if update.effective_user.id in ADMIN_IDS:
        # Tangani pesan admin terlebih dahulu
        is_admin_handled = await handle_admin_message(update, context)
        if is_admin_handled:
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
    steps = LAYANAN_STEPS[selected_service]  # Gunakan steps tanpa status

    if step_index + 1 < len(steps):
        user_data['step_index'] += 1
        next_step = steps[user_data['step_index']]
        
        if is_file_step(selected_service, next_step):
            await update.message.reply_text(f"Silakan unggah file {next_step.replace('_', ' ')} dalam format PDF, JPG, atau PNG.")
        elif is_multiple_choice_step(selected_service, next_step):
            user_data[f"{next_step}_selected"] = set()
            if hasattr(update, 'message') and update.message:
                await show_multiple_choice_options(update, context)
            else:
                await update.callback_query.message.reply_text("Menampilkan pilihan...")
                update_adapter = UpdateAdapter(update.callback_query.message)
                await show_multiple_choice_options(update_adapter, context)
        elif is_terms_step(next_step):
            if hasattr(update, 'message') and update.message:
                await show_terms_and_conditions(update, context)
            else:
                await update.callback_query.message.reply_text("Menampilkan syarat dan ketentuan...")
                await show_terms_and_conditions(UpdateAdapter(update.callback_query.message), context)
        else:
            if hasattr(update, 'message') and update.message:
                await update.message.reply_text(f"Silakan masukkan {next_step.replace('_', ' ')}:")
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.message.reply_text(f"Silakan masukkan {next_step.replace('_', ' ')}:")
    else:

        # Dapatkan user_id
        user_id = update.effective_user.id

         # Semua langkah selesai, simpan ke Google Sheets dengan user_id
        if save_to_google_sheets(user_data, selected_service, user_id):
            message_obj = update.message if hasattr(update, 'message') and update.message else update.callback_query.message
            await message_obj.reply_text("✅ Data berhasil disimpan ke Google Sheets.")
            
            # Notifikasi ke admin tentang pengajuan baru
            for admin_id in ADMIN_IDS:
                try:
                    nama = user_data.get('Nama_Lengkap', 'N/A')
                    message = f"🔔 PENGAJUAN BARU\n\n" \
                              f"Layanan: {selected_service}\n" \
                              f"Nama: {nama}\n" \
                              f"Status: {DEFAULT_STATUS}\n\n" \
                              f"Ketik /admin untuk melihat detail"
                    
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Error sending new entry notification to admin {admin_id}: {str(e)}")
        else:
            message_obj = update.message if hasattr(update, 'message') and update.message else update.callback_query.message
            await message_obj.reply_text("❌ Gagal menyimpan data ke Google Sheets.")

        # Tampilkan ringkasan data yang dimasukkan (tanpa status)
        response = f"Terima kasih, berikut data Anda untuk {selected_service}:\n" + '\n'.join(
            [f"{key.replace('_', ' ')}: {user_data.get(key, '')}" for key in steps]
        )
        
        message_obj = update.message if hasattr(update, 'message') and update.message else update.callback_query.message
        await message_obj.reply_text(response, reply_markup=ReplyKeyboardRemove())
        user_data.clear()
        
# Kelas bantuan untuk membuat objek yang kompatibel dengan update.message
class UpdateAdapter:
    def _init_(self, message):
        self.message = message

# Perbaikan fungsi handle_file untuk mengatasi masalah file lock di Windows
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data

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
    
    if not is_file_step(selected_service, current_step):
        await update.message.reply_text(f"Langkah ini tidak memerlukan file. Silakan masukkan {current_step.replace('_', ' ')}.")
        return

    file = update.message.document
    if not file:
        await update.message.reply_text("Harap kirimkan file yang sesuai.")
        return
    
    file_extension = file.file_name.split(".")[-1].lower()
    if file_extension not in ["pdf", "jpg", "png"]:
        await update.message.reply_text("Format file tidak didukung. Gunakan PDF, JPG, atau PNG.")
        return

    import time
    timestamp = int(time.time())
    file_path = f"temp_{timestamp}_{file.file_name}"
    file_info = await file.get_file()
    
    try:
         # Download file dari Telegram
        await file_info.download_to_drive(file_path)
        
        # Upload ke Google Drive
        file_metadata = {"name": file.file_name, "parents": [FOLDER_ID]}
        media = MediaFileUpload(file_path, mimetype=file.mime_type)
        uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        
        # Generate link Google Drive
        file_link = f"https://drive.google.com/file/d/{uploaded_file['id']}/view?usp=sharing"
        
        # Simpan link di user_data
        user_data[current_step] = file_link
        
        await update.message.reply_text(f"✅ File {current_step.replace('_', ' ')} berhasil diunggah!")
        
        # Pindah ke langkah berikutnya setelah memastikan media sudah di-close
        media._fd.close()  # Pastikan file ditutup sebelum mencoba menghapus
        # await file_info.download_to_drive(file_path)
        
        # # Use service-specific folder
        # FOLDER_ID = SERVICE_FOLDERS[selected_service]
        # file_metadata = {"name": file.file_name, "parents": [FOLDER_ID]}
        # media = MediaFileUpload(file_path, mimetype=file.mime_type)
        # uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        
        # file_link = f"https://drive.google.com/file/d/{uploaded_file['id']}/view?usp=sharing"
        # user_data[current_step] = file_link
        
        # await update.message.reply_text(f"✅ File {current_step.replace('_', ' ')} berhasil diunggah!")
        
        # media._fd.close()
        
    except Exception as e:
        await update.message.reply_text(f"❌ Gagal mengunggah file: {str(e)}")
    
    finally:
        time.sleep(1)
        delete_temp_file(file_path)
    
    await move_to_next_step(update, context)

# Fungsi error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("Terjadi kesalahan. Silakan coba lagi atau ketik /start untuk memulai ulang.")
    except:
        pass

# Konfigurasi bot dan polling
if __name__ == '__main__':
    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()
    
    # Tambahkan handlers
    app.add_handler(CommandHandler('start', start_command))
    # Add the admin command handler to your app
    app.add_handler(CommandHandler('admin', admin_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Tambahkan error handler
    app.add_error_handler(error_handler)
    
    print('Polling...')
    app.run_polling(poll_interval=3)