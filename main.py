import os, tempfile, asyncio, traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")

def menu(has_both=False):
    if has_both:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 EDIT TO MY BEAT NOW", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔥 OPERATOR V8.1 READY\n1. Send video (as file = better)\n2. Send MP3\n3. Click EDIT\nIf button fails, type /edit\nBaseline 3.0 Redmi fix", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fid = (update.message.video or update.message.document).file_id
    context.user_data["video"] = fid
    has_both = "video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Video saved! {'Ready to edit!' if has_both else 'Now send MP3'}", reply_markup=menu(has_both))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fid = (update.message.audio or update.message.voice or update.message.document).file_id
    context.user_data["audio"] = fid
    has_both = "video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Music saved! {'Ready to edit!' if has_both else 'Now send video'}", reply_markup=menu(has_both))

async def do_edit_logic(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("❌ Send video AND music first!")
        return
    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip
    from moviepy import vfx
    status = await update_msg.reply_text("🥁 Step 1/3: Downloading...")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"])
            af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🥁 Step 2/3: Cutting to phonk beat (140 BPM)... This takes 1-2 min, don't press again.")
            def process():
                vclip=VideoFileClip(v_in)
                if vclip.w>720: vclip=vclip.resized(width=720)
                aclip=AudioFileClip(a_in)
                dur=min(vclip.duration, aclip.duration, 12)
                vclip=vclip.subclipped(0,dur); aclip=aclip.subclipped(0,dur)
                beat=60.0/140.0; clips=[]; t=0; idx=0
                while t<dur:
                    nxt=min(t+beat*2, dur)
                    seg=vclip.subclipped(t,nxt)
                    seg=seg.with_effects([vfx.MultiplySpeed(1.8 if idx%2==0 else 0.7)])
                    clips.append(seg)
                    if idx%3==0: clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.05))
                    t=nxt; idx+=1
                final=concatenate_videoclips(clips).with_audio(aclip)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None,
                    ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2","-b:v","2000k"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Step 3/3: Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ DONE - Beat sync 140BPM - Baseline 3.0 - Should play on Redmi")
            await status.delete()
    except Exception as e:
        tb = traceback.format_exc()[-3500:]
        await update_msg.reply_text(f"❌ Edit crashed, here's why:\n{e}\n\n{tb}\n\nSend this to me")
        try: await status.delete()
        except: pass

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    await do_edit_logic(q.message, context)

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await do_edit_logic(update.message, context)

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_button))
    app.run_polling()

if __name__=="__main__": main()
