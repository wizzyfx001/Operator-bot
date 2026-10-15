import os, tempfile, asyncio, traceback, random, numpy as np, requests, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION=20

def menu(v=0,a=False):
    kb=[]
    if v>0 and a: kb.append([InlineKeyboardButton(f"🔥 SMART Edit V24.6 ({v} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {v} | Audio: {'Yes' if a else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    context.user_data["videos"]=[]; context.user_data["search_results"]=[]
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text("👋 V24.6 - NO COOKIES NEEDED\nJust send YouTube link OR /search burna boy\nIt will auto-set audio", reply_markup=menu())

async def on_video(update, context):
    if "videos" not in context.user_data: context.user_data["videos"]=[]
    fid=(update.message.video or update.message.document).file_id
    context.user_data["videos"].append(fid)
    v=len(context.user_data["videos"])
    await update.message.reply_text(f"✅ Video {v} added", reply_markup=menu(v, "audio" in context.user_data))

async def on_audio(update, context):
    context.user_data["audio"]=(update.message.audio or update.message.voice or update.message.document).file_id
    v=len(context.user_data.get("videos",[]))
    await update.message.reply_text(f"✅ Audio saved", reply_markup=menu(v, True))

async def download_youtube_direct(video_id, status_msg=None):
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        out_template=os.path.join(tmp, "audio.%(ext)s")
        final_mp3=os.path.join(tmp, "final.mp3")

        # THIS IS THE FIX - No cookies needed, uses TV clients bypass
        ydl_opts={
            'format':'bestaudio/best',
            'outtmpl':out_template,
            'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}],
            'quiet':True,
            'no_warnings':True,
            'extractor_args':{
                'youtube':{
                    'player_client':['android','android_music','android_mediaconnect','ios','web'],
                    'player_skip':['webpage','configs']
                }
            },
            'js_runtimes':{'node':{}},
            'nocheckcertificate':True,
        }

        def do_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            # find mp3
            for f in os.listdir(tmp):
                if f.startswith("audio.") and (f.endswith(".mp3") or f.endswith(".m4a") or f.endswith(".webm")):
                    src=os.path.join(tmp,f)
                    if not src.endswith(".mp3"):
                        # convert already done by postprocessor
                        pass
                    # find actual mp3
            # postprocessor creates audio.mp3
            mp3=os.path.join(tmp,"audio.mp3")
            if os.path.exists(mp3):
                return mp3
            # check any mp3
            for f in os.listdir(tmp):
                if f.endswith(".mp3"):
                    return os.path.join(tmp,f)
            return None

        mp3_path=await asyncio.to_thread(do_dl)
        if mp3_path and os.path.exists(mp3_path):
            # copy to persistent temp for telegram upload
            persistent=os.path.join(tempfile.gettempdir(), f"yt_{video_id}.mp3")
            import shutil
            shutil.copy(mp3_path, persistent)
            return persistent
        return None

async def on_youtube_link(update, context):
    url=update.message.text.strip()
    m=re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,})', url)
    if not m: return
    video_id=m.group(1)
    status=await update.message.reply_text(f"⬇️ Downloading on Railway (NO COOKIES NEEDED): {video_id}...\nUsing TV bypass...")
    try:
        mp3_path=await download_youtube_direct(video_id, status)
        if mp3_path and os.path.exists(mp3_path):
            sent=await update.message.reply_audio(audio=open(mp3_path,'rb'), caption="✅ Downloaded direct! Audio auto-set")
            context.user_data["audio"]=sent.audio.file_id
            v=len(context.user_data.get("videos",[]))
            await status.edit_text(f"✅ Audio set! Now send videos + click SMART Edit", reply_markup=menu(v, True))
            try: os.remove(mp3_path)
            except: pass
        else:
            await status.edit_text("❌ Still blocked. Try /search and different song, or send Spotify link instead.")
    except Exception as e:
        await status.edit_text(f"Error: {str(e)[:400]}")

async def search_cmd(update, context):
    query=" ".join(context.args)
    if not query: return await update.message.reply_text("Use: /search burna boy OR send YouTube link")
    status=await update.message.reply_text(f"🔍 Searching: {query}...")
    try:
        import yt_dlp
        ydl_opts={'quiet':True,'skip_download':True,'extract_flat':True,'extractor_args':{'youtube':{'player_client':['android','web']}}}
        def do_search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch5:{query}", download=False)
        result=await asyncio.to_thread(do_search)
        entries=[e for e in result.get('entries',[]) if e][:5]
        if not entries: await status.edit_text("No results"); return
        context.user_data["search_results"]=entries
        buttons=[[InlineKeyboardButton(f"🎵 {e.get('title','')[:45]}", callback_data=f"yt_{i}")] for i,e in enumerate(entries)]
        await status.edit_text("Tap to download (V24.6 direct, no Kiwi, no cookies):", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e: await status.edit_text(f"Search error: {e}")

async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send video + audio first. For audio, just send YouTube link!"); return
    status=await update_msg.reply_text(f"⏳ V24.6 SMART processing...")
    try:
        from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
        import moviepy.video.fx.all as vfx
        with tempfile.TemporaryDirectory() as tmp:
            vfiles=[]
            for i,fid in enumerate(context.user_data["videos"]):
                p=os.path.join(tmp,f"v{i}.mp4"); f=await context.bot.get_file(fid); await f.download_to_drive(p); vfiles.append(p)
            a_in=os.path.join(tmp,"a.mp3"); out=os.path.join(tmp,"out.mp4")
            af=await context.bot.get_file(context.user_data["audio"]); await af.download_to_drive(a_in)
            def process():
                vclips=[VideoFileClip(p) for p in vfiles]; aclip=AudioFileClip(a_in); song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclips[0].size; cool=[]
                try:
                    import cv2
                    for vc in vclips:
                        for t in np.arange(0.3, max(0.4, vc.duration-0.7), 0.45):
                            try:
                                f1=vc.get_frame(t); f2=vc.get_frame(t+0.45)
                                if np.mean(f1)<10 or np.mean(f2)<10: continue
                                g1=cv2.cvtColor(f1, cv2.COLOR_RGB2GRAY); g2=cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                                move=np.mean(cv2.absdiff(g1,g2)); cool.append((vc,t,move))
                            except: continue
                    cool.sort(key=lambda x: x[2], reverse=True)
                    filt=[]; used=[]
                    for vc,t,s in cool:
                        if all(abs(t-u)>0.9 for u in used): filt.append((vc,t,s)); used.append(t)
                    cool=filt[:20]
                except:
                    for vc in vclips:
                        for i in range(8): cool.append((vc, i*0.8, 0))
                clips=[]; total=0; idx=0
                while total<song_dur and idx<len(cool):
                    vc,t,_=cool[idx]; idx+=1
                    if t+0.4>vc.duration: continue
                    seg=vc.subclip(t, t+0.38).resize((W,H))
                    zoom=1.35
                    if idx<=4:
                        seg_z=seg.resize(zoom).crop(x_center=W/2+random.randint(-10,10), y_center=H/2, width=W, height=H).fx(vfx.speedx, 2.0)
                        clips.append(seg_z); clips.append(seg_z.fx(vfx.time_mirror)); total+=0.76
                    else:
                        seg_z=seg.resize(zoom).crop(x_center=W/2, y_center=H/2, width=W, height=H).fx(vfx.speedx, random.uniform(1.7,2.1))
                        clips.append(seg_z); total+=0.38
                merged=concatenate_videoclips(clips, method="compose")
                if merged.duration<song_dur: merged=merged.loop(duration=song_dur+0.2)
                final_main=merged.subclip(0, song_dur).crop(y1=int(H*0.08), y2=H, x1=0, x2=W).resize((W,H))
                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.03), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.5)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except: final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None, ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"])
                for vc in vclips: vc.close(); aclip.close(); final.close(); merged.close()
            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V24.6")
            await status.delete()
    except Exception as e: await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-800:]}")

async def on_btn(update, context):
    q=update.callback_query; await q.answer()
    d=q.data
    if d=="edit": await do_edit(q.message, context)
    elif d=="clear":
        context.user_data["videos"]=[]; context.user_data["search_results"]=[]
        if "audio" in context.user_data: del context.user_data["audio"]
        await q.message.edit_text("🗑 Cleared", reply_markup=menu(0,False))
    elif d.startswith("yt_"):
        try:
            idx=int(d.split("_")[1])
            entries=context.user_data.get("search_results",[])
            item=entries[idx]
            video_id=item.get('id') or item.get('url','').split('v=')[-1]
            status=await q.message.reply_text(f"⬇️ Direct download (bypass): {item.get('title','')[:40]}...")
            mp3_path=await download_youtube_direct(video_id, status)
            if mp3_path and os.path.exists(mp3_path):
                sent=await q.message.reply_audio(audio=open(mp3_path,'rb'), title=item.get('title','')[:40], caption="✅ Auto-set as audio!")
                context.user_data["audio"]=sent.audio.file_id
                v=len(context.user_data.get("videos",[]))
                await status.edit_text(f"✅ Audio set! Now send videos", reply_markup=menu(v, True))
                try: os.remove(mp3_path)
                except: pass
            else:
                await status.edit_text(f"Failed for {video_id}, try another song")
        except Exception as e: await q.message.reply_text(f"Fail: {e}")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.Regex(r'(https?://)?(www\.)?(youtube\.com|youtu\.be)'), on_youtube_link))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.run_polling()
if __name__=="__main__": main()
