from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, ContextTypes, PollAnswerHandler
import asyncio
import random
import json

QUIZ_DATA = "quiz.json"  # Savollarni saqlagan faylingiz
MAX_OPTION_LENGTH = 100  # Telegram opsiya uzunligi limiti

# Savollarni yuklash funksiyasi
def load_quiz_data(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

quiz_data = load_quiz_data(QUIZ_DATA)

def shuffle_options(question):
    """Variantlarni tasodifiy aralashtiradi va to'g'ri javob indeksini yangilaydi."""
    options = question["options"]
    correct_answer = question["correct_answer"]

    # Variantlarni indekslari bilan birga olish
    indexed_options = list(enumerate(options))
    random.shuffle(indexed_options)

    # Yangi variantlar va to'g'ri javob indeksini hisoblash
    shuffled_options = [opt for _, opt in indexed_options]
    new_correct_answer = [i for i, (orig_idx, _) in enumerate(indexed_options) if orig_idx == correct_answer][0]

    question["options"] = shuffled_options
    question["correct_answer"] = new_correct_answer
    return question

def truncate_options(options):
    """Variantlarni maksimal uzunligini cheklaydi."""
    return [opt[:MAX_OPTION_LENGTH] for opt in options]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botni boshlash komandasi."""
    await update.message.reply_text(
        "Salom! Quizni boshlash uchun /quiz ni bosing va nechta savol xohlayotganingizni yozing (masalan: /quiz 5)!"
    )

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tasodifiy savollarni yuboradi."""
    chat_id = update.effective_chat.id

    # Foydalanuvchidan savollar sonini olish
    try:
        num_questions = int(context.args[0])
        if num_questions <= 0 or num_questions > len(quiz_data):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text(
            f"Iltimos, to'g'ri sonni kiriting (1 dan {len(quiz_data)} gacha)!"
        )
        return

    # Tasodifiy savollarni tanlash
    selected_questions = random.sample(quiz_data, num_questions)

    context.user_data["quiz_questions"] = selected_questions
    context.user_data["quiz_current_index"] = 0
    context.user_data["quiz_correct_answers"] = 0
    context.user_data["chat_id"] = chat_id

    await send_next_question(context)

async def send_next_question(context: ContextTypes.DEFAULT_TYPE):
    current_index = context.user_data["quiz_current_index"]
    selected_questions = context.user_data["quiz_questions"]

    if current_index >= len(selected_questions):
        correct_answers = context.user_data["quiz_correct_answers"]
        total_questions = len(selected_questions)
        chat_id = context.user_data["chat_id"]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Quiz tugadi! Sizning natijangiz: {correct_answers} dan {total_questions}. Keyingi savollar uchun yana /quiz ni bosing!"
        )
        return

    question = selected_questions[current_index]
    shuffled_question = shuffle_options(question)

    # Variantlar uzunligini cheklash
    options = truncate_options(shuffled_question["options"])
    correct_option = shuffled_question["correct_answer"]

    if any(len(opt) == 0 for opt in options):
        await context.bot.send_message(
            chat_id=context.user_data["chat_id"],
            text="Xato: Variantlar uzunligi cheklangan! Keyingi savolga o'tamiz."
        )
        context.user_data["quiz_current_index"] += 1
        await send_next_question(context)
        return

    message = await context.bot.send_poll(
        chat_id=context.user_data["chat_id"],
        question=f"[{current_index + 1}/{len(selected_questions)}] {shuffled_question['question']}",
        options=options,
        type=Poll.QUIZ,
        correct_option_id=correct_option,
        is_anonymous=False,
        open_period=15  # 30 soniya vaqt
    )

    # Natijani saqlash va timeoutni boshqarish
    context.user_data["quiz_poll_id"] = message.poll.id
    context.bot_data[message.poll.id] = {
        "chat_id": context.user_data["chat_id"],
        "message_id": message.message_id,
        "correct_option": correct_option,
        "processed": False,
    }

    # 30 soniyadan keyin avtomatik o'tish
    asyncio.create_task(timeout_poll(context, message.poll.id))

async def timeout_poll(context: ContextTypes.DEFAULT_TYPE, poll_id: str):
    """Vaqt tugaganda avtomatik keyingi savolga o'tish."""
    await asyncio.sleep(30)
    if poll_id in context.bot_data and not context.bot_data[poll_id]["processed"]:
        context.bot_data[poll_id]["processed"] = True
        context.user_data["quiz_current_index"] += 1
        del context.bot_data[poll_id]
        await send_next_question(context)

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi javobni belgilasa keyingi savolga o'tadi."""
    poll_id = update.poll_answer.poll_id
    user_selected = update.poll_answer.option_ids[0]

    if poll_id not in context.bot_data:
        return

    poll_data = context.bot_data[poll_id]

    if poll_data["processed"]:
        return

    poll_data["processed"] = True
    correct_option = poll_data["correct_option"]

    if user_selected == correct_option:
        context.user_data["quiz_correct_answers"] += 1

    context.user_data["quiz_current_index"] += 1
    del context.bot_data[poll_id]
    await send_next_question(context)

def main():
    application = Application.builder().token("7753802100:AAH_IiDmMv6Mng_K1lnjkIJId1lFZVij5C4").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("quiz", quiz))
    application.add_handler(PollAnswerHandler(handle_poll_answer))

    application.run_polling()

if __name__ == "__main__":
    main()
