import os, tempfile, asyncio, traceback, random, numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION = 20
COOKIE_FILE = "cookies.txt" if os.path.exists("cookies.txt") else None
print(f"COOKIE FILE: {COOKIE_FILE} -> {'FOUND' if COOKIE_FILE else 'NOT FOUND'}")

def menu(videos=0, has_audio=False):
    kb=[]
    if videos>0 and has_audio:
        kb.append([InlineKeyboardButton(f"🔥 SMART Edit ({videos} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {videos} | Audio: {'Yes' if has_audio else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear All", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["videos"]=[]
    if "audio" in context.user_data: del context.user_data["audio"]
    msg = "✅ Cookies loaded - YouTube will work" if COOKIE_FILE else "❌ Add cookies.txt to GitHub to fix YouTube"
    await update.message.reply_text(f"👋 Wizzyfx V23.1 FINAL SMART\n{msg}\n\nSend MANY videos as FILE\nThen /search or send audio as FILE\n\nAuto features: No black, portrait fix, reverse on dunks", reply_markup=menu())

async def on_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "videos" not in context.user_data: context.user_data["videos"]=[]
    fid=(update.message.video or update.message.document).file_id
    context.user_data["videos"].append(fid)
    v=len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Video {v} saved! Total {v} videos", reply_markup=menu(v, "audio" in context.user_data))

async def on_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    v=len(context.user_data.get("videos",[]))
    await update.message.reply_text(f"✅ Audio saved!", reply_markup=menu(v, True))

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=" ".join(context.args)
    if not query:
        await update.message.reply_text("Use: /search the box"); return
    status=await update.message.reply_text(f"🔍 Searching: {query} (using cookies)...")
    try:
        import yt_dlp
        ydl_opts={
            'quiet':True,
            'skip_download':True,
            'extract_flat':True,
            'cookiefile': COOKIE_FILE, # <-- CHROME COOKIES HERE
            'extractor_args': {'youtube': {'player_client': ['android','web']}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result=ydl.extract_info(f"ytsearch5:{query} phonk", download=False)
        buttons=[]
        for entry in result['entries'][:5]:
            buttons.append([InlineKeyboardButton(f"🎵 {entry['title'][:40]}", callback_data=f"pick_{entry['id']}")])
        await status.edit_text(f"Found:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await status.edit_text(f"Search failed, need cookies.txt: {e}")

async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send at least 1 video + 1 audio"); return
    status=await update_msg.reply_text(f"⏳ V23.1 SMART analyzing {len(context.user_data['videos'])} videos for cool moments (dunks, drifts)...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            video_files=[]
            for idx, fid in enumerate(context.user_data["videos"]):
                p=os.path.join(tmp,f"v{idx}.mp4")
                f=await context.bot.get_file(fid); await f.download_to_drive(p)
                video_files.append(p)
            a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            af=await context.bot.get_file(context.user_data["audio"]); await af.download_to_drive(a_in)

            def process():
                vclips=[VideoFileClip(p) for p in video_files]
                aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclips[0].size
                cool_segments=[]
                try:
                    import cv2
                    for vc in vclips:
                        scores=[]; dur=vc.duration
                        for t in np.arange(0.2, max(0.3, dur-0.6), 0.3):
                            try:
                                f1=vc.get_frame(t); f2=vc.get_frame(t+0.3)
                                g1=cv2.cvtColor(f1, cv2.COLOR_RGB2GRAY); g2=cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                                move=np.mean(cv2.absdiff(g1,g2))
                                scores.append((vc, t, move))
                            except: continue
                        scores.sort(key=lambda x: x[2], reverse=True)
                        cool_segments.extend(scores[:8])
                    cool_segments.sort(key=lambda x: x[2], reverse=True)
                except Exception as e:
                    print(f"CV2 fail: {e}")
                    for vc in vclips:
                        for _ in range(8): cool_segments.append((vc, random.uniform(0, max(0, vc.duration-1)), 0))

                clips=[]; total=0; idx=0
                while total < song_dur + 0.7 and idx < len(cool_segments):
                    vc, t, score = cool_segments[idx]; idx+=1
                    cut=0.38
                    seg=vc.subclip(t, min(t+cut, vc.duration))
                    zoom=1.38
                    is_super = idx <= 5
                    if is_super:
                        seg_z=seg.resize(zoom).crop(x_center=W/2+random.randint(-15,15), y_center=H/2, width=W, height=H).fx(vfx.speedx, 2.0)
                        clips.append(seg_z)
                        clips.append(seg_z.fx(vfx.time_mirror))
                        total+=cut*2
                    else:
                        seg_z=seg.resize(zoom).crop(x_center=W/2, y_center=H/2, width=W, height=H).fx(vfx.speedx, random.uniform(1.7,2.2))
                        clips.append(seg_z)
                        total+=cut

                merged=concatenate_videoclips(clips, method="compose")
                if merged.duration < song_dur: merged=merged.loop(duration=song_dur+0.5)
                final_main=merged.subclip(0, song_dur)
                final_main=final_main.crop(y1=int(H*0.08), y2=H, x1=0, x2=W).resize((W,H)) # remove TikTok watermark + keep portrait

                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.032), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.55)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except:
                    final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)

                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None, ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart","-vf","scale=trunc(iw/2)*2:trunc(ih/2)*2"])
                for vc in vclips: vc.close()
                aclip.close(); final.close(); merged.close()

            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading SMART edit...")
            await update_msg.reply_video(video=open(out,'rb'), caption=f"✅ V23.1 SMART - Cool moments + Reverse - No black - Portrait fixed")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-1200:]}")

async def on_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q=update.callback_query; await q.answer()
    if q.data=="edit": await do_edit(q.message, context)
    elif q.data=="clear":
        context.user_data["videos"]=[];
        if "audio" in context.user_data: del context.user_data["audio"]
        await q.message.edit_text("🗑 Cleared.", reply_markup=menu(0, False))
    elif q.data.startswith("pick_"):
        vid=q.data[5:]
        status=await q.message.reply_text("⬇️ Downloading with Chrome cookies...")
        try:
            import yt_dlp
            with tempfile.TemporaryDirectory() as tmp:
                ydl_opts={
                    'format':'bestaudio/best',
                    'outtmpl':os.path.join(tmp,'audio.%(ext)s'),
                    'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3'}],
                    'quiet':True,
                    'cookiefile': COOKIE_FILE, # <-- CHROME COOKIES ADDED HERE TOO
                    'extractor_args': {'youtube': {'player_client': ['android']}},
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={vid}"])
                mp3=None
                for f in os.listdir(tmp):
                    if f.endswith(".mp3"): mp3=os.path.join(tmp,f)
                if mp3:
                    await q.message.reply_audio(audio=open(mp3,'rb'), caption="✅ Downloaded via cookies! Now send this file back as FILE to set it")
                    await status.delete()
                else: await status.edit_text("No mp3 found")
        except Exception as e:
            await status.edit_text(f"Even with cookies failed: {e}\nRe-export cookies.txt (Netscape format) and re-upload")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.run_polling()
if __name__=="__main__": main()
