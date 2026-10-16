import os, tempfile, asyncio, traceback, random, numpy as np, re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION=20

def menu(v=0,a=False):
    kb=[]
    if v>0 and a: kb.append([InlineKeyboardButton(f"🔥 BEAT SYNC Edit V24.7 ({v} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {v} | Audio: {'Yes' if a else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    context.user_data["videos"]=[]; context.user_data["search_results"]=[]
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text("👋 V24.7 - BEAT SYNC\nCuts now ON BEAT, not random\nSend YouTube link OR /search + videos", reply_markup=menu())

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

async def download_youtube_direct(video_id):
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        out_template=os.path.join(tmp, "audio.%(ext)s")
        ydl_opts={
            'format':'bestaudio/best',
            'outtmpl':out_template,
            'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':'192'}],
            'quiet':True,
            'no_warnings':True,
            'extractor_args':{'youtube':{'player_client':['android','android_music','android_mediaconnect','ios','web'], 'player_skip':['webpage','configs']}},
        }
        def do_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            mp3=os.path.join(tmp,"audio.mp3")
            return mp3 if os.path.exists(mp3) else None
        mp3_path=await asyncio.to_thread(do_dl)
        if mp3_path and os.path.exists(mp3_path):
            persistent=os.path.join(tempfile.gettempdir(), f"yt_{video_id}.mp3")
            import shutil; shutil.copy(mp3_path, persistent)
            return persistent
        return None

async def on_youtube_link(update, context):
    url=update.message.text.strip()
    m=re.search(r'(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{6,})', url)
    if not m: return
    video_id=m.group(1)
    status=await update.message.reply_text(f"⬇️ Downloading: {video_id}...")
    try:
        mp3_path=await download_youtube_direct(video_id)
        if mp3_path:
            sent=await update.message.reply_audio(audio=open(mp3_path,'rb'), caption="✅ Auto-set as audio!")
            context.user_data["audio"]=sent.audio.file_id
            v=len(context.user_data.get("videos",[]))
            await status.edit_text(f"✅ Audio set!", reply_markup=menu(v, True))
            try: os.remove(mp3_path)
            except: pass
        else: await status.edit_text("Failed, try another")
    except Exception as e: await status.edit_text(f"Error: {e}")

async def search_cmd(update, context):
    query=" ".join(context.args)
    if not query: return await update.message.reply_text("Use: /search burna boy")
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
        await status.edit_text("Tap to download:", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e: await status.edit_text(f"Search error: {e}")

# THIS IS THE FIX FOR YOUR COMPLAINT - BEAT SYNC
async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send video + audio first!"); return
    status=await update_msg.reply_text(f"⏳ V24.7 - Analyzing BEAT of song...")
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
                vclips=[VideoFileClip(p) for p in vfiles]
                aclip=AudioFileClip(a_in)
                song_dur=min(aclip.duration, MAX_DURATION)
                W,H=vclips[0].size

                # --- BEAT DETECTION (THIS FIXES YOUR ISSUE) ---
                import librosa
                try:
                    y, sr = librosa.load(a_in, duration=song_dur+1)
                    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
                    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
                    # Filter beats within song duration
                    beat_times = [t for t in beat_times if t < song_dur-0.2]
                    if len(beat_times) < 5: # fallback if beat detection fails
                        beat_times = list(np.arange(0.3, song_dur, 0.5))
                except Exception as e:
                    print(f"Beat detection failed {e}, using 0.5s")
                    beat_times = list(np.arange(0.3, song_dur, 0.5))

                # Create cool moments
                cool=[]
                try:
                    import cv2
                    for vc in vclips:
                        for t in np.arange(0.3, vc.duration-0.8, 0.4):
                            try:
                                f1=vc.get_frame(t);
                                if np.mean(f1)<8: continue
                                g1=cv2.cvtColor(f1, cv2.COLOR_RGB2GRAY)
                                # motion score
                                f2=vc.get_frame(t+0.3)
                                g2=cv2.cvtColor(f2, cv2.COLOR_RGB2GRAY)
                                move=np.mean(cv2.absdiff(g1,g2))
                                cool.append((vc,t,move))
                            except: continue
                    cool.sort(key=lambda x: x[2], reverse=True)
                except:
                    for vc in vclips:
                        for i in range(15): cool.append((vc, i*0.5, 0))

                # --- BUILD CLIPS ON BEAT ---
                clips=[]
                last_cool_idx=0
                for i in range(len(beat_times)-1):
                    beat_start=beat_times[i]
                    beat_end=beat_times[i+1]
                    beat_dur=beat_end-beat_start
                    if beat_dur>1.2: beat_dur=0.5
                    if beat_dur<0.18: beat_dur=0.18

                    # Pick best clip
                    if last_cool_idx>=len(cool): last_cool_idx=0
                    vc,t,_=cool[last_cool_idx]; last_cool_idx+=1
                    if t+beat_dur>vc.duration: t=max(0, vc.duration-beat_dur-0.1)

                    seg=vc.subclip(t, t+beat_dur).resize((W,H))

                    # BEAT EFFECTS: On every 2nd beat, add zoom punch
                    if i%2==0:
                        seg=seg.resize(1.25).crop(x_center=W/2+random.randint(-15,15), y_center=H/2, width=W, height=H)
                    if i%4==0: # Every 4th beat = heavy 808, speed up
                        seg=seg.fx(vfx.speedx, 1.6)
                    if i%8==0: # Mirror for funk style
                        seg=seg.fx(vfx.mirror_x)

                    clips.append(seg)

                merged=concatenate_videoclips(clips, method="compose")
                if merged.duration<song_dur: merged=merged.loop(duration=song_dur+0.1)
                final_main=merged.subclip(0, song_dur).crop(y1=int(H*0.07), y2=H, x1=0, x2=W).resize((W,H))

                try:
                    wm=TextClip("Wizzyfx", fontsize=int(H*0.03), color='white', font='DejaVu-Sans').set_duration(song_dur).set_position((0.02,0.92), relative=True).set_opacity(0.5)
                    final=CompositeVideoClip([final_main, wm], size=(W,H)).set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)
                except: final=final_main.set_audio(aclip.subclip(0,song_dur)).set_duration(song_dur)

                final.write_videofile(out, codec="libx264", audio_codec="aac", preset="ultrafast", threads=2, logger=None, ffmpeg_params=["-pix_fmt","yuv420p","-movflags","+faststart"])
                for vc in vclips: vc.close()
                aclip.close(); final.close(); merged.close()

            await asyncio.to_thread(process)
            await status.edit_text("📤 Uploading beat-synced edit...")
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V24.7 BEAT SYNC - cuts on beat now!")
            await status.delete()
    except Exception as e: await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-1000:]}")

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
            status=await q.message.reply_text(f"⬇️ Downloading: {item.get('title','')[:40]}...")
            mp3_path=await download_youtube_direct(video_id)
            if mp3_path and os.path.exists(mp3_path):
                sent=await q.message.reply_audio(audio=open(mp3_path,'rb'), title=item.get('title','')[:40], caption="✅ Auto-set!")
                context.user_data["audio"]=sent.audio.file_id
                v=len(context.user_data.get("videos",[]))
                await status.edit_text(f"✅ Audio set!", reply_markup=menu(v, True))
                try: os.remove(mp3_path)
                except: pass
            else: await status.edit_text(f"Failed")
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
