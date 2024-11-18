import pyautogui
import time
from PIL import Image
import io
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
from elevenlabs import ElevenLabs, VoiceSettings
import base64
from openai import OpenAI
import os
import subprocess
from dotenv import load_dotenv

# Load environment variables at the start of the file
load_dotenv()

# Configure OpenAI client
def setup_openai():
    """Setup OpenAI API client"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    return OpenAI(api_key=api_key)

def capture_screenshot():
    """Capture a screenshot and return it as a PIL Image"""
    screenshot = pyautogui.screenshot()
    return screenshot

def encode_pil_image(pil_image):
    """Convert PIL Image to base64 string"""
    img_byte_arr = io.BytesIO()
    pil_image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return base64.b64encode(img_byte_arr).decode('utf-8')

def process_image_with_gpt4(client, image):
    """Process image with GPT-4o-mini for Japanese text translation"""
    base64_image = encode_pil_image(image)
    
    prompt = """
    Please extract any Japanese text from this image and translate it to English.
    Also provide the romaji (Latin alphabet) reading.
    Format your response exactly like this:
    Japanese: [extracted Japanese text]
    Romaji: [romaji reading]
    English: [English translation]
    
    If no Japanese text is found, respond with "No Japanese text detected."
    """
    

    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error processing image: {str(e)}"

def parse_gpt4_response(text):
    """Parse the response from GPT-4 into Japanese, Romaji and English text"""
    try:
        print("Parsing response:", text)  # Debug print
        lines = text.split('\n')
        japanese_text = ""
        romaji_text = ""
        english_text = ""
        
        for line in lines:
            if line.startswith('Japanese:'):
                japanese_text = line.replace('Japanese:', '').strip()
            elif line.startswith('Romaji:'):
                romaji_text = line.replace('Romaji:', '').strip()
            elif line.startswith('English:'):
                english_text = line.replace('English:', '').strip()
        
        print(f"Parsed: Japanese='{japanese_text}', Romaji='{romaji_text}', English='{english_text}'")
        return japanese_text, romaji_text, english_text
    except Exception as e:
        print(f"Error parsing GPT-4 response: {str(e)}")
        return None, None, None



class TranslatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Japanese Translator")
        
        # Set window to appear on left side of screen
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = 400
        window_height = screen_height - 100
        self.root.geometry(f"{window_width}x{window_height}+0+0")
        
        # Create main frame
        main_frame = ttk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        self.capture_btn = ttk.Button(controls_frame, text="Start Capture", command=self.toggle_capture)
        self.capture_btn.pack(side=tk.LEFT, padx=5)
        
        self.interval_var = tk.StringVar(value="5")
        ttk.Label(controls_frame, text="Interval (s):").pack(side=tk.LEFT, padx=5)
        ttk.Entry(controls_frame, textvariable=self.interval_var, width=5).pack(side=tk.LEFT)
        
        # Add reference button
        self.ref_btn = ttk.Button(controls_frame, text="Reference", command=self.show_reference_sheet)
        self.ref_btn.pack(side=tk.LEFT, padx=5)
        
        # Output area
        self.output_area = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=20)
        self.output_area.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Initialize variables
        self.capturing = False
        self.client = setup_openai()
        self.capture_thread = None
        
        # Initialize Eleven Labs
        self.setup_tts()
        self.last_spoken_text = None
        
        # Add TTS controls
        tts_frame = ttk.Frame(controls_frame)
        tts_frame.pack(side=tk.LEFT, padx=5)
        
        self.play_btn = ttk.Button(
            tts_frame, 
            text="▶️",
            width=3,
            command=self.play_last_message
        )
        self.play_btn.pack(side=tk.LEFT, padx=2)
        
        # Add TTS toggle
        self.tts_enabled = tk.BooleanVar(value=True)
        self.tts_checkbox = ttk.Checkbutton(
            tts_frame, 
            text="Auto TTS", 
            variable=self.tts_enabled
        )
        self.tts_checkbox.pack(side=tk.LEFT)
        
        # Bind keyboard shortcuts
        self.root.bind('<Control-r>', lambda e: self.show_reference_sheet())
        self.root.bind('<Control-space>', lambda e: self.play_last_message())
        self.root.bind('<Control-t>', lambda e: self.tts_checkbox.invoke())
        
        # Initialize chat history and translations toggle
        self.chat_history = []
        self.show_translations = tk.BooleanVar(value=True)

    def setup_tts(self):
        """Setup Eleven Labs TTS"""
        api_key = os.getenv("ELEVEN_LABS_API_KEY")
        if not api_key:
            raise ValueError("ELEVEN_LABS_API_KEY not found in environment variables")
        self.eleven_labs = ElevenLabs(api_key=api_key)
        self.voice_settings = VoiceSettings(
            stability=0.71,
            similarity_boost=0.5,
            style=0.0,
        )

    def toggle_capture(self):
        if not self.capturing:
            self.capturing = True
            self.capture_btn.config(text="Stop Capture")
            self.capture_thread = threading.Thread(target=self.capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
        else:
            self.capturing = False
            self.capture_btn.config(text="Start Capture")

    def capture_loop(self):
        last_hash = None
        
        def get_image_hash(image):
            """Convert image to a simple hash for comparison"""
            small_image = image.resize((32, 32), Image.Resampling.BILINEAR)
            gray_image = small_image.convert('L')
            pixels = list(gray_image.getdata())
            avg = sum(pixels) / len(pixels)
            return ''.join('1' if pixel > avg else '0' for pixel in pixels)

        while self.capturing:
            try:
                screenshot = capture_screenshot()
                current_hash = get_image_hash(screenshot)
                
                if current_hash != last_hash:
                    response = process_image_with_gpt4(self.client, screenshot)
                    japanese_text, romaji_text, english_text = parse_gpt4_response(response)
                    
                    if japanese_text and english_text:
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        entry = {
                            'timestamp': timestamp,
                            'japanese': japanese_text,
                            'romaji': romaji_text,
                            'english': english_text
                        }
                        
                        output = f"\n[{timestamp}]\n🇯🇵 {japanese_text}\n📝 {romaji_text}\n"
                        if self.show_translations.get():
                            output += f"🇺🇸 {english_text}"
                        output += "\n" + "─" * 40
                        
                        self.chat_history.append(entry)
                        self.output_area.insert(tk.END, output)
                        self.output_area.see(tk.END)
                        
                        if self.tts_enabled.get() and japanese_text != self.last_spoken_text:
                            self.speak_japanese(japanese_text)
                            self.last_spoken_text = japanese_text
                    
                    last_hash = current_hash
                
                interval = int(self.interval_var.get())
                time.sleep(interval)
                
            except Exception as e:
                print(f"Error in capture loop: {str(e)}")
                self.capturing = False
                self.root.after(0, self.capture_btn.config, {"text": "Start Capture"})
                break

    def speak_japanese(self, text):
        """Generate and play TTS for Japanese text"""
        try:
            if not text:
                return
                
            audio_stream = self.eleven_labs.text_to_speech.convert_as_stream(
                text=text,
                voice_id="3JDquces8E8bkmvbh6Bc",
                model_id="eleven_turbo_v2_5",
                voice_settings=self.voice_settings
            )
            
            temp_file = "temp_audio.mp3"
            with open(temp_file, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            
            try:
                subprocess.run(['mpv', temp_file], check=True)
            except FileNotFoundError:
                if os.name == 'nt':
                    os.startfile(temp_file)
                elif os.name == 'posix':
                    subprocess.run(['open', temp_file])
                else:
                    print("Error: Could not find a suitable media player")
            except subprocess.CalledProcessError as e:
                print(f"Error playing audio: {e}")
            
            time.sleep(0.5)
            try:
                os.remove(temp_file)
            except:
                pass
            
        except Exception as e:
            print(f"TTS Error: {str(e)}")

    def play_last_message(self):
        """Play the most recent Japanese message"""
        if self.chat_history:
            latest_entry = self.chat_history[-1]
            japanese_text = latest_entry.get('japanese')
            if japanese_text:
                self.speak_japanese(japanese_text)
                self.last_spoken_text = japanese_text

    def speak_japanese(self, text):
        """Generate and play TTS for Japanese text"""
        try:
            # Skip if text is empty or None
            if not text:
                return
                
            # Generate audio using Eleven Labs
            audio_stream = self.eleven_labs.text_to_speech.convert_as_stream(
                text=text,
                voice_id="3JDquces8E8bkmvbh6Bc",
                model_id="eleven_turbo_v2_5",
                voice_settings=self.voice_settings
            )
            
            # Save audio to temporary file
            temp_file = "temp_audio.mp3"
            with open(temp_file, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            
            # Try mpv first, fall back to system default player if not available
            try:
                subprocess.run(['mpv', temp_file], check=True)
            except FileNotFoundError:
                # On Windows, use start command
                if os.name == 'nt':
                    os.startfile(temp_file)
                # On macOS, use open command
                elif os.name == 'posix':
                    subprocess.run(['open', temp_file])
                else:
                    print("Error: Could not find a suitable media player")
            except subprocess.CalledProcessError as e:
                print(f"Error playing audio: {e}")
            
            # Clean up temp file after a short delay to ensure playback has started
            time.sleep(0.5)
            try:
                os.remove(temp_file)
            except:
                pass
            
        except Exception as e:
            print(f"TTS Error: {str(e)}")

    def toggle_tts(self):
        """Toggle TTS on/off"""
        if self.tts_enabled.get():
            print("TTS enabled")
        else:
            print("TTS disabled")

    def show_reference_sheet(self):
        """Open a new window with hiragana and katakana reference"""
        ref_window = tk.Toplevel(self.root)
        ref_window.title("Japanese Reference")
        ref_window.geometry("600x800")
        
        # Create notebook for tabs
        notebook = ttk.Notebook(ref_window)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Hiragana tab
        hiragana_frame = ttk.Frame(notebook)
        notebook.add(hiragana_frame, text='Hiragana')
        hiragana_text = scrolledtext.ScrolledText(hiragana_frame, wrap=tk.WORD)
        hiragana_text.pack(fill='both', expand=True)
        hiragana_text.insert(tk.END, """
        Basic Hiragana:
        あ (a) い (i) う (u) え (e) お (o)
        か (ka) き (ki) く (ku) け (ke) こ (ko)
        さ (sa) し (shi) す (su) せ (se) そ (so)
        た (ta) ち (chi) つ (tsu) て (te) と (to)
        な (na) に (ni) ぬ (nu) ね (ne) の (no)
        は (ha) ひ (hi) ふ (fu) へ (he) ほ (ho)
        ま (ma) み (mi) む (mu) め (me) も (mo)
        や (ya) ゆ (yu) よ (yo)
        ら (ra) り (ri) る (ru) れ (re) ろ (ro)
        わ (wa) を (wo) ん (n)

        Dakuten (゛) and Handakuten (゜):
        が (ga) ぎ (gi) ぐ (gu) げ (ge) ご (go)
        ざ (za) じ (ji) ず (zu) ぜ (ze) ぞ (zo)
        だ (da) ぢ (ji) づ (zu) で (de) ど (do)
        ば (ba) び (bi) ぶ (bu) べ (be) ぼ (bo)
        ぱ (pa) ぴ (pi) ぷ (pu) ぺ (pe) ぽ (po)

        Small Characters (Combinations):
        きょ (kyo) しゃ (sha) ちゅ (chu) にょ (nyo)
        ぎょ (gyo) じゃ (ja) ぢゅ (ju) みょ (myo)
        びょ (byo) ぴょ (pyo)

        Special Characters:
        っ (small tsu - doubles following consonant)
        ー (long vowel mark)
        """)
        
        # Katakana tab
        katakana_frame = ttk.Frame(notebook)
        notebook.add(katakana_frame, text='Katakana')
        katakana_text = scrolledtext.ScrolledText(katakana_frame, wrap=tk.WORD)
        katakana_text.pack(fill='both', expand=True)
        katakana_text.insert(tk.END, """
        Basic Katakana:
        ア (a) イ (i) ウ (u) エ (e) オ (o)
        カ (ka) キ (ki) ク (ku) ケ (ke) コ (ko)
        サ (sa) シ (shi) ス (su) セ (se) ソ (so)
        タ (ta) チ (chi) ツ (tsu) テ (te) ト (to)
        ナ (na) ニ (ni) ヌ (nu) ネ (ne) ノ (no)
        ハ (ha) ヒ (hi) フ (fu) ヘ (he) ホ (ho)
        マ (ma) ミ (mi) ム (mu) メ (me) モ (mo)
        ヤ (ya) ユ (yu) ヨ (yo)
        ラ (ra) リ (ri) ル (ru) レ (re) ロ (ro)
        ワ (wa) ヲ (wo) ン (n)

        Dakuten (゛) and Handakuten (゜):
        ガ (ga) ギ (gi) グ (gu) ゲ (ge) ゴ (go)
        ザ (za) ジ (ji) ズ (zu) ゼ (ze) ゾ (zo)
        ダ (da) ヂ (ji) ヅ (zu) デ (de) ド (do)
        バ (ba) ビ (bi) ブ (bu) ベ (be) ボ (bo)
        パ (pa) ピ (pi) プ (pu) ペ (pe) ポ (po)

        Small Characters (Combinations):
        キョ (kyo) シャ (sha) チュ (chu) ニョ (nyo)
        ギョ (gyo) ジャ (ja) ヂュ (ju) ミョ (myo)
        ビョ (byo) ピョ (pyo)

        Special Characters:
        ッ (small tsu - doubles following consonant)
        ー (long vowel mark)
        
        Common Foreign Sound Combinations:
        ファ (fa) フィ (fi) フェ (fe) フォ (fo)
        ヴァ (va) ヴィ (vi) ヴ (vu) ヴェ (ve) ヴォ (vo)
        ウィ (wi) ウェ (we) ウォ (wo)
        チェ (che) シェ (she) ジェ (je)
        ティ (ti) ディ (di) デュ (du)
        """)

def main():
    root = tk.Tk()
    app = TranslatorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
