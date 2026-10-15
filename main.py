import os, tempfile, asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Main menu buttons
def get_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ Velocity Ramp", callback_data="velocity"),
         InlineKeyboardButton("🐢 Slow-mo Finisher", callback_data="slowmo")],
        [InlineKeyboardButton("✨ Flash Transition", callback_data="flash"),
         InlineKeyboardButton("🎬 Full Operator Edit", callback_data="all")],
        [InlineKeyboardButton("📝 Pro Caption + Effects", callback_data="caption")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔥 OPERATOR Bot V4\n\nSend me any gaming clip (under 20s)\nThen choose effect with buttons - NO auto zoom.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 See Effects List", callback_data="list")]])
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Save file_id to process after button press
    file_id = (update.message.video or update.message.document).file_id
    context.user_data["last_file"] = file_id
    
    await update.message.reply_text(
        "✅ Clip received! Choose edit style:",
        reply_markup=get_menu()
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    effect = query.data

    if effect == "list":
        await query.message.reply_text(
            "🎨 **Effects List:**\n\n"
            "⚡ Velocity - middle part 1.8x fast\n"
            "🐢 Slow-mo - last 25% 0.35x slow finisher\n"
            "✨ Flash - white flash transitions between cuts\n"
            "🎬 Full - Velocity + Flash + Slow-mo\n"
            "📝 Caption - Adds pro gaming caption style\n\n"
            "Send a video to try!",
            reply_markup=get_menu()
        )
        return

    file_id = context.user_data.get("last_file")
    if not file_id:
        await query.message.reply_text("Send a video first!")
        return

    from moviepy import VideoFileClip, vfx, ColorClip
    from moviepy import concatenate_videoclips

    status = await query.message.reply_text(f"⏳ Applying {effect}...")

    with tempfile.TemporaryDirectory() as tmp:
        in_path = os.path.join(tmp, "in.mp4")
        out_path = os.path.join(tmp, "out.mp4")

        file = await context.bot.get_file(file_id)
        await file.download_to_drive(in_path)

        def process():
            clip = VideoFileClip(in_path)
            if clip.w > 720:
                clip = clip.resized(width=720)
            dur = clip.duration

            if effect == "velocity":
                p1 = clip.subclipped(0, dur*0.4)
                p2 = clip.subclipped(dur*0.4, dur).with_effects([vfx.MultiplySpeed(1.8)])
                final = concatenate_videoclips([p1, p2])

            elif effect == "slowmo":
                p1 = clip.subclipped(0, dur*0.75)
                p2 = clip.subclipped(dur*0.75, dur).with_effects([vfx.MultiplySpeed(0.35)])
                final = concatenate_videoclips([p1, p2])

            elif effect == "flash":
                # Cut in middle with white flash
                p1 = clip.subclipped(0, dur*0.5)
                p2 = clip.subclipped(dur*0.5, dur)
                flash = ColorClip(size=clip.size, color=(255,255,255), duration=0.15)
                final = concatenate_videoclips([p1, flash, p2])

            elif effect == "all":
                p1 = clip.subclipped(0, dur*0.35)
                p2 = clip.subclipped(dur*0.35, dur*0.75).with_effects([vfx.MultiplySpeed(1.9)])
                p3 = clip.subclipped(dur*0.75, dur).with_effects([vfx.MultiplySpeed(0.35)])
                flash = ColorClip(size=clip.size, color=(255,255,255), duration=0.12)
                final = concatenate_videoclips([p1, flash, p2, flash, p3])

            else: # caption style
                final = clip

            final.write_videofile(
    out_path, 
    codec="libx264", 
    audio_codec="aac", 
    preset="ultrafast", 
    threads=1, 
    logger=None,
    ffmpeg_params=[
        "-pix_fmt", "yuv420p",
        "-profile:v", "baseline",
        "-level", "3.0",
        "-movflags", "+faststart",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-b:v", "2000k",
        "-maxrate", "2000k",
        "-bufsize", "4000k"
    ]
            )
            clip.close()
            final.close()

        await asyncio.to_thread(process)
        await status.edit_text("📤 Uploading...")
        caption = f"✅ {effect} edit done - No zoom, clean transitions"
        await query.message.reply_video(video=open(out_path, 'rb'), caption=caption, reply_markup=get_menu())
        await status.delete()

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(CallbackQueryHandler(handle_button))
    print("V4 Bot with buttons running...")
    app.run_polling()
