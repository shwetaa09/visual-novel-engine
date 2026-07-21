import streamlit as st
import os
import json
import requests
from dotenv import load_dotenv
import google.generativeai as genai
from gtts import gTTS


# PHASE 1: The Director's Cut (UI & Configuration)


load_dotenv()

st.set_page_config(page_title="Visual Novel Engine", page_icon="📖")
st.title("📖 The Multi-Modal Visual Novel")


@st.cache_resource
def get_gemini_client():
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    return genai


genai_client = get_gemini_client()

st.sidebar.title("Story Settings")

genre = st.sidebar.selectbox(
    "Story Genre",
    ["Fantasy", "Sci-Fi", "Horror", "Mystery", "Cyberpunk"]
)

art_style = st.sidebar.selectbox(
    "Art Style",
    ["Anime", "Realistic", "Watercolor", "Pixel Art", "Comic Book"]
)

if "history" not in st.session_state:
    st.session_state.history = []
if "chat" not in st.session_state:
    st.session_state.chat = None
if "story_started" not in st.session_state:
    st.session_state.story_started = False


# PHASE 2: System prompt forcing strict JSON output

SYSTEM_PROMPT = f"""
You are the narrator of an interactive visual novel in the {genre} genre.

STRICT RULES:
- You must ALWAYS reply with ONLY a valid JSON object. No markdown, no code fences, no extra text.
- The JSON object must have exactly these keys:
  1. "story_text": a short narrative paragraph (3-5 sentences) continuing the story.
  2. "image_prompt": a highly detailed, descriptive prompt (for an AI image generator) that
     visually represents the current scene, written in a {art_style} art style.
  3. "options": a list of 2 to 3 short strings, each representing a distinct choice the
     reader can make next.

Example format:
{{"story_text": "...", "image_prompt": "...", "options": ["Option A", "Option B", "Option C"]}}

Never break character. Never include any text outside the JSON object.
"""


def get_model():
    return genai_client.GenerativeModel(
        model_name="gemini-flash-latest",
        system_instruction=SYSTEM_PROMPT
    )


def parse_ai_response(raw_text):
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "story_text": raw_text,
            "image_prompt": "a mysterious fantasy scene",
            "options": ["Continue"]
        }


def generate_image(image_prompt):
    try:
        url = f"https://image.pollinations.ai/prompt/{image_prompt}?width=768&height=512"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception:
        st.toast("🖼️ Image server is busy, skipping visual...")
        return None


def generate_audio(story_text):
    try:
        tts = gTTS(text=story_text, lang="en")
        audio_path = "narration.mp3"
        tts.save(audio_path)
        return audio_path
    except Exception:
        st.toast("🔊 Audio narration failed, continuing without sound...")
        return None


def advance_story(user_choice):
    try:
        response = st.session_state.chat.send_message(user_choice)
        parsed = parse_ai_response(response.text)
    except Exception:
        st.toast("⚠️ The AI is busy, please try again in a moment...")
        return

    image_bytes = generate_image(parsed.get("image_prompt", ""))
    audio_path = generate_audio(parsed.get("story_text", ""))

    st.session_state.history.append({
        "story_text": parsed.get("story_text", ""),
        "image_bytes": image_bytes,
        "audio_path": audio_path,
        "options": parsed.get("options", ["Continue"])
    })


if not st.session_state.story_started:
    st.write("Set your genre and art style in the sidebar, then begin your adventure!")
    if st.button("🚀 Begin the Adventure"):
        model = get_model()
        st.session_state.chat = model.start_chat(history=[])
        st.session_state.story_started = True
        advance_story("Start the story.")
        st.rerun()
else:
    if st.sidebar.button("🔄 Restart Story"):
        st.session_state.history = []
        st.session_state.chat = None
        st.session_state.story_started = False
        st.rerun()


# PHASE 4: Render story history (text + image + audio)

for i, entry in enumerate(st.session_state.history):
    st.markdown(f"### Chapter {i + 1}")
    st.write(entry["story_text"])

    if entry["image_bytes"]:
        st.image(entry["image_bytes"])

    if entry["audio_path"]:
        st.audio(entry["audio_path"])

    st.divider()


# PHASE 3: Dynamic UI Generation (buttons from AI's options)

if st.session_state.story_started and st.session_state.history:
    latest_options = st.session_state.history[-1]["options"]

    st.markdown("### What do you do next?")
    cols = st.columns(len(latest_options))

    for idx, option_text in enumerate(latest_options):
        with cols[idx]:
            if st.button(option_text, key=f"option_{len(st.session_state.history)}_{idx}"):
                advance_story(option_text)
                st.rerun()