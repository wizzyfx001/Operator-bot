import os, tempfile, asyncio, traceback
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
BOT_TOKEN=os.getenv("BOT_TOKEN")
def menu(has_both=False):
    if has_both: return InlineKeyboardMarkup([[InlineKeyboardButton("🔥 EDIT TO MY BEAT NOW", callback_data="edit")]])
    return InlineKeyboardMarkup([[InlineKeyboardButton("How it works", callback_data="help")]])
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔥 V8.3 FINAL FIX\n1. Video as FILE\n2. MP3 as FILE\n3. /edit", reply_markup=menu())
async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["video"]=(update.message.video or update.message.document).file_id
    has_both="video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Video saved! {'Ready!' if has_both else 'Now send MP3'}", reply_markup=menu(has_both))
async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    has_both="video" in context.user_data and "audio" in context.user_data
    await update.message.reply_text(f"✅ Music saved! {'Ready!' if has_both else 'Now send video'}", reply_markup=menu(has_both))
async def do_edit(update_msg, context):
    if "video" not in context.user_data or "audio" not in context.user_data:
        await update_msg.reply_text("❌ Send both first!"); return
    status=await update_msg.reply_text("🥁 Step 1/3: Downloading...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, ColorClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            v_in=os.path.join(tmp,"v.mp4"); a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            vf=await context.bot.get_file(context.user_data["video"]); af=await context.bot.get_file(context.user_data["audio"])
            await vf.download_to_drive(v_in); await af.download_to_drive(a_in)
            await status.edit_text("🥁 Step 2/3: Cutting... 1-2 min")
            def process():
                vclip=VideoFileClip(v_in)
                if vclip.w>720: vclip=vclip.resize(width=720)
                aclip=AudioFileClip(a_in)
                dur=min(vclip.duration, aclip.duration, 12)
                vclip=vclip.subclip(0,dur); aclip=aclip.subclip(0,dur)
                beat=60.0/140.0; clips=[]; t=0; idx=0
                while t<dur:
                    nxt=min(t+beat*2, dur)
                    seg=vclip.subclip(t,nxt)
                    seg=seg.fx(vfx.speedx, 1.8 if idx%2==0 else 0.7)
                    clips.append(seg)
                    if idx%3==0:
                        clips.append(ColorClip(size=vclip.size, color=(255,255,255), duration=0.05))
                    t=nxt; idx+=1
                final=concatenate_videoclips(clips)
                final=final.set_audio(aclip)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=1, logger=None, ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","baseline","-level","3.0","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                vclip.close(); aclip.close(); final.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Step 3/3: Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ DONE - Baseline 3.0 Redmi fix")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"❌ CRASH:\n{e}\n\n{traceback.format_exc()[-3000:]}")
async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer(); await do_edit(q.message, context)
async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await do_edit(update.message, context)
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn)); app.run_polling()
if __name__=="__main__": main()
