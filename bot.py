import os
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.types import Message
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv
import mimetypes

TOKEN = "7744907120:AAFMlbTr48G3HpRWt-fIxh_ku6mxz87HjP8"
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

class ConvertStates(StatesGroup):
    waiting_for_format = State()
    waiting_for_bitrate = State()
    waiting_for_resolution = State()
    waiting_for_codec = State()

user_data = {}

AUDIO_FORMATS = ["mp3", "wav", "flac", "aac"]
VIDEO_FORMATS = ["mp4", "avi", "mkv", "mov"]
DOC_FORMATS = ["pdf", "docx"]
BITRATES = ["128k", "256k", "512k", "1M", "2M"]
RESOLUTIONS = ["640x360", "1280x720", "1920x1080"]
CODECS = ["libx264", "libx265", "libvpx-vp9"]

@dp.message_handler(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "👋 Привет! Отправь мне файл — аудио, видео или документ, и я помогу его конвертировать."
    )

@dp.message_handler(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📄 Команды:\n/start — начать\n/help — помощь\n/info — информация о последнем файле"
    )

@dp.message_handler(Command("info"))
async def info_command(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data or "file_path" not in user_data[user_id]:
        await message.answer("Сначала отправьте файл.")
        return
    file_path = user_data[user_id]["file_path"]
    if not os.path.exists(file_path):
        await message.answer("Файл не найден.")
        return
    size = os.path.getsize(file_path)
    await message.answer(f"📁 Файл: {os.path.basename(file_path)}\nРазмер: {round(size / 1024, 2)} КБ")

@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.AUDIO, types.ContentType.VIDEO])
async def handle_file(message: Message, state: FSMContext):
    media = message.document or message.audio or message.video
    file_name = media.file_name or f"{media.file_id}"
    file_path = f"downloads/{file_name}"

    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    await media.download(destination_file=file_path)
    user_data[message.from_user.id] = {"file_path": file_path}

    mime, _ = mimetypes.guess_type(file_path)
    if mime:
        if mime.startswith("audio"):
            user_data[message.from_user.id]["is_video"] = False
            await offer_audio_formats(message)
        elif mime.startswith("video"):
            user_data[message.from_user.id]["is_video"] = True
            await offer_video_formats(message)
        elif file_name.endswith(".pdf"):
            user_data[message.from_user.id]["doc_type"] = "pdf"
            await offer_doc_conversion(message)
        elif file_name.endswith(".docx"):
            user_data[message.from_user.id]["doc_type"] = "docx"
            await offer_doc_conversion(message)
        else:
            await message.answer("Формат файла не поддерживается.")
    else:
        await message.answer("Не удалось определить тип файла.")

async def offer_audio_formats(message: Message):
    kb = InlineKeyboardMarkup(row_width=2)
    for fmt in AUDIO_FORMATS:
        kb.insert(InlineKeyboardButton(fmt, callback_data=f"format_{fmt}"))
    await message.answer("🎵 Выберите формат конвертации:", reply_markup=kb)
    await ConvertStates.waiting_for_format.set()

async def offer_video_formats(message: Message):
    kb = InlineKeyboardMarkup(row_width=2)
    for fmt in VIDEO_FORMATS:
        kb.insert(InlineKeyboardButton(fmt, callback_data=f"format_{fmt}"))
    await message.answer("🎥 Выберите формат конвертации:", reply_markup=kb)
    await ConvertStates.waiting_for_format.set()

async def offer_doc_conversion(message: Message):
    kb = InlineKeyboardMarkup()
    if user_data[message.from_user.id]["doc_type"] == "pdf":
        kb.add(InlineKeyboardButton("PDF → DOCX", callback_data="doc_pdf_to_word"))
    elif user_data[message.from_user.id]["doc_type"] == "docx":
        kb.add(InlineKeyboardButton("DOCX → PDF", callback_data="doc_word_to_pdf"))
    await message.answer("📄 Выберите действие:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("format_"), state=ConvertStates.waiting_for_format)
async def choose_format(callback_query: types.CallbackQuery, state: FSMContext):
    fmt = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["format"] = fmt

    kb = InlineKeyboardMarkup(row_width=2)
    for br in BITRATES:
        kb.insert(InlineKeyboardButton(br, callback_data=f"bitrate_{br}"))
    await bot.send_message(uid, "Выберите битрейт:", reply_markup=kb)
    await ConvertStates.waiting_for_bitrate.set()

@dp.callback_query_handler(lambda c: c.data.startswith("bitrate_"), state=ConvertStates.waiting_for_bitrate)
async def choose_bitrate(callback_query: types.CallbackQuery, state: FSMContext):
    bitrate = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["bitrate"] = bitrate

    if user_data[uid].get("is_video"):
        kb = InlineKeyboardMarkup(row_width=2)
        for res in RESOLUTIONS:
            kb.insert(InlineKeyboardButton(res, callback_data=f"res_{res}"))
        await bot.send_message(uid, "Выберите разрешение:", reply_markup=kb)
        await ConvertStates.waiting_for_resolution.set()
    else:
        await start_conversion(callback_query.message, uid, state)

@dp.callback_query_handler(lambda c: c.data.startswith("res_"), state=ConvertStates.waiting_for_resolution)
async def choose_resolution(callback_query: types.CallbackQuery, state: FSMContext):
    resolution = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["resolution"] = resolution

    kb = InlineKeyboardMarkup(row_width=2)
    for codec in CODECS:
        kb.insert(InlineKeyboardButton(codec, callback_data=f"codec_{codec}"))
    await bot.send_message(uid, "Выберите кодек:", reply_markup=kb)
    await ConvertStates.waiting_for_codec.set()

@dp.callback_query_handler(lambda c: c.data.startswith("codec_"), state=ConvertStates.waiting_for_codec)
async def choose_codec(callback_query: types.CallbackQuery, state: FSMContext):
    codec = callback_query.data.split("_")[1]
    uid = callback_query.from_user.id
    user_data[uid]["codec"] = codec
    await start_conversion(callback_query.message, uid, state)

@dp.callback_query_handler(lambda c: c.data.startswith("doc_"))
async def handle_doc_conversion(callback_query: types.CallbackQuery):
    uid = callback_query.from_user.id
    input_path = user_data[uid]["file_path"]
    base, ext = os.path.splitext(input_path)

    if callback_query.data == "doc_pdf_to_word":
        output_path = f"{base}.docx"
        from pdf2docx import Converter
        cv = Converter(input_path)
        cv.convert(output_path)
        cv.close()
    elif callback_query.data == "doc_word_to_pdf":
        output_path = f"{base}.pdf"
        from docx2pdf import convert
        convert(input_path, output_path)

    with open(output_path, "rb") as f:
        await bot.send_document(uid, types.InputFile(f))
    os.remove(output_path)
    os.remove(input_path)
    await bot.send_message(uid, "✅ Готово! Отправь новый файл или /start")

async def start_conversion(message: Message, uid: int, state: FSMContext):
    await message.answer("⏳ Конвертируем...")

    data = user_data[uid]
    input_path = data["file_path"]
    base, _ = os.path.splitext(input_path)
    output_path = f"{base}_converted.{data['format']}"

    cmd = ["ffmpeg", "-i", input_path, "-b:a", data["bitrate"]]

    if data.get("is_video"):
        cmd += ["-s", data["resolution"], "-c:v", data["codec"]]

    cmd.append(output_path)

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with open(output_path, "rb") as f:
            await message.answer_document(types.InputFile(f))
        os.remove(output_path)
    except subprocess.CalledProcessError as e:
        await message.answer("❌ Ошибка при конвертации.")
        print("FFmpeg error:", e)

    os.remove(input_path)
    await state.finish()
    await message.answer("✅ Готово! Можешь отправить следующий файл.")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
