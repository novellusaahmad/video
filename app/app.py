# app.py — Kids Story Generator → Reels/Shorts (All-Local, No Subscriptions)
#
# A self-hosted Streamlit app that generates children's stories, creates simple
# illustrations, narrates them with **offline TTS**, and renders platform-ready
# videos (9:16 for Instagram Reels, 16:9 for YouTube). Optional local AI hooks
# that **do not require paid APIs**:
#   • Story via Ollama (local LLMs like Llama 3.1, Mistral, Gemma)
#   • Art via Stable Diffusion WebUI (Automatic1111) running locally
#   • Voices via Piper TTS (offline) or eSpeak (offline)
#
# ▶ Run
#   1) Install ffmpeg and ensure it's on PATH
#   2) pip install -r requirements.txt   (or the inline list below)
#   3) streamlit run app.py
#
# ▶ Python deps
#   pip install streamlit moviepy pillow numpy pydub python-slugify
#   # Optional (already used if present): requests pyttsx3
#   pip install requests pyttsx3
#
# ▶ Optional local tools (no subscription)
#   • Ollama (LLMs): https://ollama.com (then: `ollama pull llama3.1:8b`)
#   • Piper TTS: https://github.com/rhasspy/piper
#       - Download a voice file (e.g. en_US-lessac-low.onnx)
#       - Set env vars: PIPER_PATH, PIPER_VOICE
#       - Example (Windows PowerShell):
#           $env:PIPER_PATH="C:/tools/piper/piper.exe"
#           $env:PIPER_VOICE="C:/tools/piper/en_US-lessac-low.onnx"
#   • Stable Diffusion WebUI: https://github.com/AUTOMATIC1111/stable-diffusion-webui
#       - Start it locally, then set SD_API=http://127.0.0.1:7860
#
# NOTE: pyttsx3 uses system voices (Windows SAPI5 / macOS NSSpeech / Linux eSpeak).

import os
import io
import json
import random
from dataclasses import dataclass
from typing import List, Tuple

import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from slugify import slugify

# Optional imports
try:
    import requests
except Exception:
    requests = None

try:
    import pyttsx3  # offline TTS via system voices
except Exception:
    pyttsx3 = None

import subprocess

# ==============================
# Configuration
# ==============================
INSTAGRAM_RES = (1080, 1920)   # 9:16
YOUTUBE_RES   = (1920, 1080)   # 16:9
FPS = 30

SD_API = os.getenv("SD_API")  # e.g. http://127.0.0.1:7860
OLLAMA_API = os.getenv("OLLAMA_API", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

PIPER_PATH = os.getenv("PIPER_PATH")       # path to piper executable
PIPER_VOICE = os.getenv("PIPER_VOICE")     # path to voice .onnx

ASSETS_DIR = "outputs"
os.makedirs(ASSETS_DIR, exist_ok=True)

# ==============================
# Data structures
# ==============================
@dataclass
class Scene:
    text: str
    prompt: str
    duration: float  # seconds

# ==============================
# Built-in rule-based story gen (always available)
# ==============================
MORALS = {
    "kindness": "Kindness makes friends and brightens the world.",
    "honesty": "Telling the truth keeps hearts light and trust strong.",
    "sharing": "Sharing turns little joys into big ones.",
    "courage": "Being brave means trying even when things feel new.",
    "curiosity": "Questions open doors to wonderful discoveries."
}

def generate_story_rule_based(title: str, age: int, theme: str, moral: str, minutes: int, num_scenes: int) -> Tuple[str, List[Scene]]:
    random.seed(title + theme + moral + str(age) + str(minutes) + str(num_scenes))
    beats = [
        ("Setup", f"Introduce {title} in a cozy place related to {theme}.") ,
        ("Call to Adventure", f"A gentle problem appears involving {theme}.") ,
        ("New Friend", "A helpful friend shares an idea."),
        ("Try and Learn", "They try a new way together."),
        ("Little Setback", "Something goes a bit wrong, but feelings are respected."),
        ("Brave Choice", "They breathe, think, and try again."),
        ("Happy Resolution", "The problem is solved kindly."),
        ("Moral", MORALS.get(moral, moral))
    ]
    while len(beats) < num_scenes:
        beats.insert(-1, ("Explore", "They notice something wonderful around them."))
    beats = beats[:num_scenes]

    scenes: List[Scene] = []
    for _, idea in beats:
        simple_adj = random.choice(["soft", "bright", "happy", "gentle", "sparkly", "cozy"]) 
        buddy = random.choice(["bunny", "panda", "fox", "kitten", "puppy", "duckling"])
        place = random.choice(["meadow", "forest", "playroom", "treehouse", "seashore", "garden"]) 
        color = random.choice(["sunny yellow", "sky blue", "leafy green", "peachy pink", "lavender"]) 
        line = (
            f"{title} and a {simple_adj} {buddy} were in the {place}. "
            f"{idea} They use {theme} to help."
        )
        prompt = (
            f"Cute children’s book illustration, {buddy} and child in a {place}, "
            f"soft lighting, pastel colors, {color}, friendly faces, simple shapes, high contrast, clean background"
        )
        base_dur = max(3.5, min(10.0, (minutes * 60) / num_scenes))
        scenes.append(Scene(text=line, prompt=prompt, duration=base_dur))

    story_title = f"{title}: A {theme.title()} Adventure"
    return story_title, scenes

# ==============================
# Local LLM story via Ollama (optional, offline)
# ==============================
LLM_PROMPT = (
    "You are a children’s storyteller. Write a short story split into SCENES. "
    "Return strict JSON with keys: title (string), scenes (array of objects with 'text' and 'prompt'). "
    "Age-appropriate (3–8), friendly tone, simple words, each scene 1–3 sentences, and a gentle arc."
)


def generate_story_ollama(title: str, age: int, theme: str, moral: str, minutes: int, num_scenes: int, model: str) -> Tuple[str, List[Scene]]:
    if not requests:
        raise RuntimeError("'requests' not installed for Ollama API.")
    payload = {
        "model": model,
        "prompt": (
            f"{LLM_PROMPT}\n"
            f"Title: {title}\n"
            f"Age: {age}\n"
            f"Theme: {theme}\n"
            f"Moral: {moral}\n"
            f"Scenes: {num_scenes}\n"
            f"Duration minutes: {minutes}\n"
            "Return only JSON."
        ),
        "stream": False,
    }
    r = requests.post(f"{OLLAMA_API}/api/generate", json=payload, timeout=180)
    r.raise_for_status()
    text = r.json().get("response", "{}")
    try:
        data = json.loads(text)
        scenes = [
            Scene(
                s.get("text", ""),
                s.get("prompt", "friendly illustration of the scene"),
                max(3.5, min(10.0, (minutes * 60) / num_scenes)),
            )
            for s in data.get("scenes", [])
        ]
        if not scenes:
            raise ValueError("No scenes in LLM output")
        return data.get("title", title), scenes[:num_scenes]
    except Exception:
        # fallback to rule based if parsing fails
        return generate_story_rule_based(title, age, theme, moral, minutes, num_scenes)

# ==============================
# Illustration generation (local SD or fallback)
# ==============================

def sd_txt2img(prompt: str, width: int, height: int) -> Image.Image:
    if not SD_API or not requests:
        raise RuntimeError("Stable Diffusion API not configured.")
    payload = {"prompt": prompt, "width": width, "height": height, "steps": 25, "sampler_index": "Euler a", "cfg_scale": 6.5}
    r = requests.post(f"{SD_API}/sdapi/v1/txt2img", json=payload, timeout=180)
    r.raise_for_status()
    data = r.json()
    import base64
    img_b64 = data["images"][0]
    return Image.open(io.BytesIO(base64.b64decode(img_b64))).convert("RGB")


def fallback_illustration(prompt: str, width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height), (255, 252, 246))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        t = y / height
        r = int(255 - 20*t)
        g = int(250 - 50*t)
        b = int(240 - 60*t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    margin = int(min(width, height) * 0.03)
    draw.rounded_rectangle([margin, margin, width - margin, height - margin], radius=margin, outline=(255, 230, 200), width=6)
    bubble_w = int(width * 0.86)
    bubble_h = int(height * 0.18)
    bx = (width - bubble_w)//2
    by = int(height * 0.72)
    draw.rounded_rectangle([bx, by, bx + bubble_w, by + bubble_h], radius=24, fill=(255, 255, 255, 230), outline=(240, 220, 200), width=4)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", size=int(bubble_h*0.28))
    except Exception:
        font = ImageFont.load_default()
    text = prompt.split(",")[0][:80]
    tw, th = draw.textlength(text, font=font), font.size
    tx = bx + (buble_w - tw)//2 if (buble_w:=bubble_w) else bx
    ty = by + (bubble_h - th)//2
    draw.text((tx, ty), text, fill=(60, 60, 60), font=font)
    return img


def make_image(prompt: str, resolution: Tuple[int, int]) -> Image.Image:
    w, h = resolution
    try:
        return sd_txt2img(prompt, w, h)
    except Exception:
        return fallback_illustration(prompt, w, h)

# ==============================
# TTS (all-local options)
# ==============================

def tts_pyttsx3(text: str, wav_path: str, voice_hint: str = None, rate_wpm: int = 170):
    if pyttsx3 is None:
        raise RuntimeError("pyttsx3 not available.")
    engine = pyttsx3.init()
    if voice_hint:
        for v in engine.getProperty('voices'):
            if voice_hint.lower() in (v.name or '').lower():
                engine.setProperty('voice', v.id)
                break
    engine.setProperty('rate', int(rate_wpm))
    engine.save_to_file(text, wav_path)
    engine.runAndWait()


def tts_piper(text: str, wav_path: str, voice_path: str = None):
    exe = PIPER_PATH
    voice = voice_path or PIPER_VOICE
    if not exe or not voice:
        raise RuntimeError("Piper not configured. Set PIPER_PATH and PIPER_VOICE.")
    # Piper reads text from stdin and writes wav via -w
    with open(wav_path, 'wb') as out:
        proc = subprocess.run([exe, "-m", voice, "-w", wav_path], input=text.encode('utf-8'), stdout=out, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            raise RuntimeError(f"Piper failed: {proc.stderr.decode('utf-8', 'ignore')}")


def tts_espeak(text: str, wav_path: str, voice: str = None):
    # eSpeak is extremely lightweight and offline
    cmd = ["espeak", "-w", wav_path, text]
    if voice:
        cmd.extend(["-v", voice])
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError(f"eSpeak failed: {proc.stderr.decode('utf-8', 'ignore')}")


def synthesize(text: str, out_wav: str, engine: str, voice_hint: str = None):
    os.makedirs(os.path.dirname(out_wav), exist_ok=True)
    if engine == "Piper (offline)":
        return tts_piper(text, out_wav)
    if engine == "eSpeak (offline)":
        return tts_espeak(text, out_wav)
    # default
    return tts_pyttsx3(text, out_wav, voice_hint)

# ==============================
# Video assembly
# ==============================

def build_video(scenes: List[Scene], resolution: Tuple[int, int], out_path: str, voice_hint: str, tts_engine: str) -> str:
    W, H = resolution
    workdir = os.path.join(ASSETS_DIR, slugify(os.path.splitext(os.path.basename(out_path))[0]))
    os.makedirs(workdir, exist_ok=True)

    clips = []
    for i, sc in enumerate(scenes, start=1):
        img = make_image(sc.prompt, (W, H))
        img_path = os.path.join(workdir, f"scene_{i:02d}.png")
        img.save(img_path)

        wav_path = os.path.join(workdir, f"scene_{i:02d}.wav")
        synthesize(sc.text, wav_path, engine=tts_engine, voice_hint=voice_hint)

        ac = AudioFileClip(wav_path)
        ic = ImageClip(img_path).set_duration(max(sc.duration, ac.duration)).set_audio(ac).resize((W, H))
        # Gentle Ken Burns
        zoom_end = 1.05
        ic = ic.fx(lambda clip: clip.resize(lambda t: 1 + (zoom_end-1) * (t / clip.duration)))
        clips.append(ic)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(out_path, fps=FPS, codec="libx264", audio_codec="aac", threads=4, preset="medium")
    for c in clips:
        c.close()
    final.close()
    return out_path

# ==============================
# Streamlit UI
# ==============================

def ui():
    st.set_page_config(page_title="Kids Story → Reels & Shorts", page_icon="📚", layout="centered")
    st.title("📚✨ Children’s Story → Instagram & YouTube Video (All Local)")
    st.caption("No subscriptions. Your compute = your only limit.")

    with st.form("story_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Hero/Story Title", value="Mina and the Moon Kite")
            age = st.slider("Target Age", 3, 9, 5)
            moral = st.selectbox("Moral", list(MORALS.keys()), index=0)
            minutes = st.slider("Approx Duration (minutes)", 1, 10, 2)
        with col2:
            theme = st.text_input("Theme/Setting", value="kindness and sky adventures")
            num_scenes = st.slider("Number of Scenes", 6, 20, 8)
            story_engine = st.selectbox("Story Engine", ["Built-in (rule-based)", "Ollama (local LLM)"])
            ollama_model = st.text_input("Ollama Model", value=OLLAMA_MODEL)

        col3, col4 = st.columns(2)
        with col3:
            tts_engine = st.selectbox("Narration Engine (Offline)", ["pyttsx3 (offline)", "Piper (offline)", "eSpeak (offline)"])
            voice_hint = st.text_input("Voice hint (pyttsx3/eSpeak)", value="")
        with col4:
            platforms = st.multiselect("Export Formats", ["Instagram Reels (9:16)", "YouTube (16:9)", "Both"], default=["Both"])
        start = st.form_submit_button("Generate Story & Render Video")

    if start:
        with st.spinner("Writing story..."):
            if story_engine == "Ollama (local LLM)":
                try:
                    story_title, scenes = generate_story_ollama(title, age, theme, moral, minutes, num_scenes, model=ollama_model)
                except Exception as e:
                    st.warning(f"Ollama failed ({e}). Falling back to built-in.")
                    story_title, scenes = generate_story_rule_based(title, age, theme, moral, minutes, num_scenes)
            else:
                story_title, scenes = generate_story_rule_based(title, age, theme, moral, minutes, num_scenes)
        st.success(f"Story ready: {story_title}")
        with st.expander("Preview Story Text"):
            for i, sc in enumerate(scenes, start=1):
                st.markdown(f"**Scene {i}.** {sc.text}")

        targets = []
        if "Both" in platforms or "Instagram Reels (9:16)" in platforms:
            targets.append((INSTAGRAM_RES, f"{ASSETS_DIR}/{slugify(story_title)}_IG_9x16.mp4"))
        if "Both" in platforms or "YouTube (16:9)" in platforms:
            targets.append((YOUTUBE_RES, f"{ASSETS_DIR}/{slugify(story_title)}_YT_16x9.mp4"))

        results = []
        for res, path in targets:
            st.info(f"Rendering: {os.path.basename(path)} @ {res[0]}x{res[1]} …")
            try:
                out = build_video(scenes, res, path, voice_hint=voice_hint, tts_engine=tts_engine)
                st.video(out)
                results.append(out)
            except Exception as e:
                st.error(f"Failed to render {path}: {e}")

        if results:
            st.success("Done! Files saved below:")
            for p in results:
                st.write(f"📁 {os.path.abspath(p)}")

        st.markdown("---")
        st.subheader("Tips & Local-Only Pro Settings")
        st.markdown(
            """
            - **Local LLMs** via **Ollama**: pull a model (e.g., `ollama pull llama3.1:8b`) and switch engine to *Ollama*.
            - **Offline voices**: set `PIPER_PATH` and `PIPER_VOICE` env vars for Piper; or use `eSpeak`/`pyttsx3`.
            - **Local art**: run Stable Diffusion WebUI and set `SD_API=http://127.0.0.1:7860`.
            - **Music**: add royalty-free background later or extend this app to mix a track.
            - **Scaling**: batch-produce by running multiple Streamlit sessions or wrapping `build_video` in a queue.
            """
        )


if __name__ == "__main__":
    ui()
