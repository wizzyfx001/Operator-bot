import os, tempfile, asyncio, traceback, random, numpy as np, requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'): PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

BOT_TOKEN=os.getenv("BOT_TOKEN")
MAX_DURATION=20

def menu(v=0,a=False):
    kb=[]
    if v>0 and a: kb.append([InlineKeyboardButton(f"🔥 SMART Edit V24.4 ({v} vids)", callback_data="edit")])
    kb.append([InlineKeyboardButton(f"Videos: {v} | Audio: {'Yes' if a else 'No'}", callback_data="status")])
    kb.append([InlineKeyboardButton("🗑 Clear", callback_data="clear")])
    return InlineKeyboardMarkup(kb)

async def start(update, context):
    context.user_data["videos"]=[]; context.user_data["search_results"]=[]
    if "audio" in context.user_data: del context.user_data["audio"]
    await update.message.reply_text("👋 V24.4 FINAL - Search + Download Fixed\n\n/search burna boy works\n/search eloy works\nNo DRM, No bot block", reply_markup=menu())

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

def piped_download(video_id, out_path):
    # TRY 1: PIPED - 8 instances
    piped_instances=[
        "https://pipedapi.kavin.rocks",
        "https://api.piped.projectsegfau.lt",
        "https://pipedapi.adminforge.de",
        "https://piped-api.lunar.icu",
        "https://pipedapi.drgns.space",
        "https://pipedapi.leptos.io",
        "https://pipedapi.r4fo.com",
        "https://api.piped.privacydev.net"
    ]
    for instance in piped_instances:
        try:
            r=requests.get(f"{instance}/streams/{video_id}", timeout=15)
            if r.status_code!=200: continue
            data=r.json()
            audios=data.get('audioStreams',[])
            if not audios: continue
            audio_url=sorted(audios, key=lambda x: x.get('bitrate',0), reverse=True)[0]['url']
            rr=requests.get(audio_url, stream=True, timeout=40)
            with open(out_path, 'wb') as f:
                for c in rr.iter_content(16384): f.write(c)
            if os.path.exists(out_path) and os.path.getsize(out_path)>5000:
                print(f"Piped success {instance}")
                return True
        except Exception as e:
            print(f"Piped fail {instance}: {e}")
            continue

    # TRY 2: INVIDIOUS - backup
    inv_instances=["https://inv.nadeko.net","https://yewtu.be","https://invidious.nerdvpn.de","https://inv.tux.pizza","https://inv.zzls.xyz"]
    for inv in inv_instances:
        try:
            r=requests.get(f"{inv}/api/v1/videos/{video_id}", timeout=15)
            if r.status_code!=200: continue
            data=r.json()
            fmts=data.get('adaptiveFormats',[]) + data.get('formatStreams',[])
            audios=[f for f in fmts if 'audio' in f.get('type','')]
            if not audios: continue
            audios=sorted(audios, key=lambda x: int(x.get('bitrate',0) or 0), reverse=True)
            url=audios[0]['url']
            rr=requests.get(url, stream=True, timeout=40)
            with open(out_path,'wb') as f:
                for c in rr.iter_content(16384): f.write(c)
            if os.path.getsize(out_path)>5000:
                print(f"Invidious success {inv}")
                return True
        except Exception as e:
            print(f"Invidious fail {inv}: {e}")
            continue

    # TRY 3: COBALT
    try:
        r=requests.post("https://api.cobalt.tools/api/json", json={"url": f"https://youtube.com/watch?v={video_id}", "aFormat":"mp3", "isAudioOnly":True}, headers={"Accept":"application/json","Content-Type":"application/json"}, timeout=20)
        j=r.json()
        durl=j.get('url')
        if durl:
            rr=requests.get(durl, stream=True, timeout=40)
            with open(out_path,'wb') as f:
                for c in rr.iter_content(16384): f.write(c)
            if os.path.getsize(out_path)>5000:
                print("Cobalt success")
                return True
    except Exception as e:
        print(f"Cobalt fail {e}")

    return False

async def search_cmd(update, context):
    query=" ".join(context.args)
    if not query: return await update.message.reply_text("Use: /search burna boy")
    status=await update.message.reply_text(f"🔍 Searching YouTube: {query}...")
    try:
        import yt_dlp
        ydl_opts={'quiet':True,'skip_download':True,'extract_flat':True,'extractor_args':{'youtube':{'player_client':['android']}}}
        def do_search():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch5:{query}", download=False)
        result=await asyncio.to_thread(do_search)
        entries=[e for e in result.get('entries',[]) if e][:5]
        if not entries:
            await status.edit_text("No results, try other words"); return
        context.user_data["search_results"]=entries
        buttons=[[InlineKeyboardButton(f"🎵 {e.get('title','')[:45]}", callback_data=f"yt_{i}")] for i,e in enumerate(entries)]
        await status.edit_text("YouTube results (tap to download - works for Naija & foreign):", reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        await status.edit_text(f"Search error: {e}")

async def do_edit(update_msg, context):
    if not context.user_data.get("videos") or "audio" not in context.user_data:
        await update_msg.reply_text("Send video + audio first"); return
    status=await update_msg.reply_text(f"⏳ V24.4 SMART processing {len(context.user_data['videos'])} vids...")
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
            await update_msg.reply_video(video=open(out,'rb'), caption="✅ V24.4 FINAL - No black, No repeat, Portrait fixed")
            await status.delete()
    except Exception as e:
        await update_msg.reply_text(f"Error: {e}\n{traceback.format_exc()[-800:]}")

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
            if idx>=len(entries): await q.message.reply_text("Search again, expired"); return
            item=entries[idx]
            video_id=item.get('id')
            if not video_id:
                url=item.get('url','')
                video_id=url.split('v=')[-1] if 'v=' in url else url.split('/')[-1]
            status=await q.message.reply_text(f"⬇️ Downloading: {item.get('title','')[:40]}...\nTrying 13 servers...")
            with tempfile.TemporaryDirectory() as tmp:
                mp3_path=os.path.join(tmp,"song.mp3")
                ok=await asyncio.to_thread(piped_download, video_id, mp3_path)
                if ok and os.path.exists(mp3_path):
                    await q.message.reply_audio(audio=open(mp3_path,'rb'), title=item.get('title','')[:40], caption="✅ Downloaded! Now SEND THIS AUDIO BACK AS FILE to set it for edit")
                    await status.delete()
                else:
                    await status.edit_text(f"All 13 servers busy for {video_id}. Try again in 1 min or try different song. This happens when many people download same time.")
        except Exception as e:
            await q.message.reply_text(f"Fail: {e}")

def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, on_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE | filters.Document.AUDIO, on_audio))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.run_polling()

if __name__=="__main__": main()
