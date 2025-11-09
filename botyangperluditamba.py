import pytesseract
from pdf2image import convert_from_path
from fuzzywuzzy import fuzz

# Tambahi dibawah dictionary dan diatas admin command handler
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

expected_sections_2 = [
    "SURAT PERINTAH PERMOHONAN",
    "Menimbang",
    "Dasar",
    "Memberi Permohonan",
    "Kepada",
    "Nama",
    "NIP",
    "Jabatan",
    "Untuk",
    "Dengan ini meminta permohan untuk mendapatkan fasilitas video coference",
    "Hal-hal yang terkait syarat dan ketentuan yang ada saya terima dan melaksanakan dengan sebaik baiknya."
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

    # Bandingkan tiap bagian dengan fuzzy matching
    matching_scores = []
    for section in expected_sections:
        score = fuzz.partial_ratio(section, extracted_text)
        matching_scores.append(score)
    
    avg_similarity = sum(matching_scores) / len(matching_scores)

    print(f"Hasil OCR (Teks yang diekstrak):\n{extracted_text}")
    print(f"Tingkat Kemiripan Rata-rata: {avg_similarity:.2f}%")

    return avg_similarity >= threshold  # PDF Sesuai

def check_pdf_with_ocr_2(pdf_path, threshold=70):
    """Memeriksa apakah teks dalam PDF sesuai dengan format yang diharapkan."""
    extracted_text = extract_text_from_pdf(pdf_path)

    # Bandingkan tiap bagian dengan fuzzy matching
    matching_scores = []
    for section in expected_sections_2:
        score = fuzz.partial_ratio(section, extracted_text)
        matching_scores.append(score)
    
    avg_similarity = sum(matching_scores) / len(matching_scores)

    print(f"Hasil OCR (Teks yang diekstrak):\n{extracted_text}")
    print(f"Tingkat Kemiripan Rata-rata: {avg_similarity:.2f}%")

    return avg_similarity >= threshold  # PDF Sesuai
### PEMBATAS AKHIR PDF CHEK

# Tambahi diatas handle_file
async def upload_to_drive(file_path, file_name, selected_service):
    # Tentukan folder ID berdasarkan layanan
    folder_id = SERVICE_FOLDERS.get(selected_service)
    if not folder_id:
        return None, "❌ Konfigurasi folder untuk layanan ini tidak ditemukan."
    
    # Tentukan mime type
    mime_type = "application/pdf" if file_name.endswith('.pdf') else "image/jpeg"
    
    media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
    
    try:
        # Upload file dengan progress monitoring
        uploaded_file = drive_service.files().create(
            body={
                "name": file_name,
                "parents": [folder_id]
            }, 
            media_body=media, 
            fields="id,webViewLink"
        ).execute()
        
        # Dapatkan link file
        file_id = uploaded_file.get('id')
        
        # Ubah permission agar bisa diakses dengan link
        drive_service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            fields="id"
        ).execute()
        
        # Dapatkan link sharing yang dapat diakses
        file_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        
        return file_link, None  # Kembalikan link dan tidak ada error
    except Exception as e:
        return None, f"❌ Gagal mengunggah file ke Drive: {str(e)}"

# batas
# tambahi diatas eror_handler
#### Update handle_file

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

    # File bisa dikirim sebagai document atau photo
    if update.message.document:
        file = update.message.document
        file_name = file.file_name
    elif update.message.photo:
        file = update.message.photo[-1]  # Ambil kualitas tertinggi
        file_name = f"photo_{int(datetime.datetime.now().timestamp())}.jpg"
    else:
        await update.message.reply_text("Harap kirimkan file yang sesuai (dokumen atau foto).")
        return
    
    # Validasi format file jika itu adalah document
    if update.message.document:
        file_extension = file_name.split(".")[-1].lower()
        if file_extension not in ["pdf", "jpg", "jpeg", "png"]:
            await update.message.reply_text("Format file tidak didukung. Gunakan PDF, JPG, atau PNG.")
            return

    # Gunakan timestamp untuk menghindari konflik nama file
    import time
    timestamp = int(time.time())
    file_path = f"temp_{timestamp}_{file_name}" if hasattr(file, 'file_name') else f"temp_{timestamp}.jpg"
    
    try:
        # Dapatkan info file dan download
        file_info = await context.bot.get_file(file.file_id)
        await file_info.download_to_drive(file_path)
        
        # Tunggu sebentar untuk memastikan file sudah benar-benar terdownload
        await asyncio.sleep(1)
        
        # Periksa apakah file berhasil didownload
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            await update.message.reply_text("❌ Gagal mendownload file. Silakan coba lagi.")
            return
        
        # Notifikasi file sedang diproses
        status_message = await update.message.reply_text("⏳ Sedang memeriksa file...")

        # Cek apakah file PDF sesuai dengan format yang diharapkan
        if selected_service == "Reset/Permintaan Akun Cpanel" and current_step == "Surat_Tugas":
            if check_pdf_with_ocr(file_path):
                await status_message.edit_text("✅ File PDF sesuai dengan format yang diharapkan.")
                # Simpan link ke user_data
               # Panggil fungsi untuk mengunggah ke Google Drive
                file_link, error_message = await upload_to_drive(file_path, file_name, selected_service)
                
                if error_message:
                    await status_message.edit_text(error_message)
                    return
                
                # Simpan link ke user_data
                user_data[current_step] = file_link  # Simpan link yang diunggah
                
                await move_to_next_step(update, context)  # Lanjut ke langkah berikutnya
            else:
                await status_message.edit_text("❌ File PDF tidak sesuai dengan format yang diharapkan. Harap kirimkan lagi File yang benar.")
                return  # Minta pengguna untuk mengupload file lagi
            
        ##### SURAT PERMOHONAN: Cek apakah file PDF sesuai dengan format surat permohonan yang diharapkan
        if selected_service == "Permohonan Video Conference" and current_step == "Surat_Permohonan":
            if check_pdf_with_ocr_2(file_path):
                await status_message.edit_text("✅ File PDF sesuai dengan format yang diharapkan.")
                # Simpan link ke user_data
               # Panggil fungsi untuk mengunggah ke Google Drive
                file_link, error_message = await upload_to_drive(file_path, file_name, selected_service)
                
                if error_message:
                    await status_message.edit_text(error_message)
                    return
                
                # Simpan link ke user_data
                user_data[current_step] = file_link  # Simpan link yang diunggah
                
                await move_to_next_step(update, context)  # Lanjut ke langkah berikutnya
            else:
                await status_message.edit_text("❌ File PDF tidak sesuai dengan format yang diharapkan. Harap kirimkan lagi File yang benar.")
                return  # Minta pengguna untuk mengupload file lagi
        else:
            # Lanjutkan ke langkah berikutnya untuk file lainnya
            await move_to_next_step(update, context)

    except Exception as e:
        logger.error(f"Error handling file: {str(e)}")
        await update.message.reply_text(f"❌ Terjadi kesalahan: {str(e)}")
        return
    
    finally:
        # Hapus file sementara
        # delete_temp_file(file_path)
          # Pastikan media file ditutup jika ada
        # if 'media' in locals() and hasattr(media, '_fd') and media._fd:
        #     try:
        #         media._fd.close()
        #     except:
        #         pass
        # Hapus file sementara
        try:
            await asyncio.sleep(2)  # Beri waktu untuk memastikan operasi selesai
            delete_temp_file(file_path)
        except Exception as clean_error:
            logger.error(f"Error cleaning up temp file: {str(clean_error)}")
    
    # Lanjutkan ke langkah berikutnya
    await move_to_next_step(update, context)

