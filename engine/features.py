import json
import os
from pipes import quote
import re
import sqlite3
import struct
import subprocess
import time
import webbrowser
from playsound import playsound
import eel
import pyaudio
import pyautogui
from engine.command import speak, is_online
from engine.config import ASSISTANT_NAME, GROQ_API_KEY
from engine.helper import extract_yt_term, markdown_to_text, remove_words
from gpt4all import GPT4All
from groq import Groq

# Playing assiatnt sound function
import pywhatkit as kit
import pvporcupine

import datetime

con = sqlite3.connect("jarvis.db")
cursor = con.cursor()

def get_setting_val(key):
    try:
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = cursor.fetchone()
        return result[0] if result else None
    except:
        return None

@eel.expose
def playAssistantSound():
    music_dir = "www\\assets\\audio\\start_sound.mp3"
    playsound(music_dir)

def hotword():
    porcupine=None
    paud=None
    audio_stream=None
    try:
        # pre trained keywords    
        porcupine=pvporcupine.create(keywords=["jarvis","alexa"]) 
        paud=pyaudio.PyAudio()
        audio_stream=paud.open(rate=porcupine.sample_rate,channels=1,format=pyaudio.paInt16,input=True,frames_per_buffer=porcupine.frame_length)
        
        # loop for streaming
        while True:
            keyword=audio_stream.read(porcupine.frame_length)
            keyword=struct.unpack_from("h"*porcupine.frame_length,keyword)

            # processing keyword comes from mic 
            keyword_index=porcupine.process(keyword)

            # checking first keyword detetcted for not
            if keyword_index>=0:
                print("hotword detected")

                # pressing shorcut key win+j
                import pyautogui as autogui
                autogui.keyDown("win")
                autogui.press("j")
                time.sleep(2)
                autogui.keyUp("win")
                
    except:
        if porcupine is not None:
            porcupine.delete()
        if audio_stream is not None:
            audio_stream.close()
        if paud is not None:
            paud.terminate()
            
from AppOpener import open as appopen

# ... existing code ...

def openCommand(query):
    query = query.replace(ASSISTANT_NAME, "")
    query = query.replace("open", "")
    query.lower()

    app_name = query.strip()

    if app_name != "":
        try:
            cursor.execute(
                'SELECT path FROM sys_command WHERE name IN (?)', (app_name,))
            results = cursor.fetchall()

            if len(results) != 0:
                speak("Opening "+query)
                os.startfile(results[0][0])

            elif len(results) == 0: 
                cursor.execute(
                'SELECT url FROM web_command WHERE name IN (?)', (app_name,))
                results = cursor.fetchall()
                
                if len(results) != 0:
                    speak("Opening "+query)
                    webbrowser.open(results[0][0])

                else:
                    speak("Opening "+query)
                    try:
                        # Try using AppOpener first
                        # We use match_closest=True to find best match automatically
                        appopen(app_name, match_closest=True, output=False)
                    except:
                        try:
                             os.system('start '+query)
                        except:
                             speak("not found")
        except:
            speak("some thing went wrong")

# ... existing code ...

def llama_chat(query):
    try:
        if GROQ_API_KEY == "Your-Groq-API-Key":
             return "Please configure your Groq API Key in settings."
        
        system_prompt = "You are a helpful assistant named Jarvis. Please keep your responses short, concise, and sweet. Do not give lengthy explanations unless asked."

        client = Groq(api_key=GROQ_API_KEY)
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": query,
                }
            ],
            model="llama-3.1-8b-instant",
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        print(f"Llama Error: {e}")
        return None

def offline_chat(query):
    try:
        # Load model only when needed to save resources? Or keep loaded?
        # For responsiveness, keeping it loaded is better, but takes RAM.
        # Check if we have a model file.
        model_name = "Meta-Llama-3-8B-Instruct.Q4_0.gguf" # Example model
        # Check if model exists locally to avoid auto-download loop
        # GPT4All(..., allow_download=False) might be the key if supported, 
        # but let's just wrap it.
        # Actually simplest is just to turn off allow_download.
        model = GPT4All(model_name, allow_download=False)
        
        system_prompt = "You are a helpful assistant named Jarvis. Please keep your responses short, concise, and sweet."
        
        # GPT4All generate doesn't support system prompt separate param easily in simple generate
        # But we can try to structure prompt: "System: ... \n User: ... "
        full_prompt = f"System: {system_prompt}\nUser: {query}\nAssistant:"
        
        output = model.generate(full_prompt, max_tokens=100)
        return output
    except Exception as e:
        print(f"Offline Chat Error: {e}")
        return "I am having trouble running offline mode."

# Main Chat Handler
def chatBot(query):
    user_input = query.lower()
    
    # Check Offline Mode Setting
    offline_mode = get_setting_val('offline_mode')
    
    if offline_mode == 'true' or not is_online():
        print("Using Offline Mode")
        response = offline_chat(user_input)
    else:
        print("Using Online Mode (Llama)")
        response = llama_chat(user_input)
        
        # If Llama fails (e.g. network glitch or API error), ask to go offline
        if response is None:
             speak("I am facing connectivity issues and offline mode is not fully configured.")
             # Removed auto-fallback to prevent unwanted downloads
             # response = offline_chat(user_input)
             response = "Connectivity Error."

    print(response)
    speak(response)
    # return response

# Settings Modal 

@eel.expose
def getSettings():
    cursor.execute("SELECT * FROM settings")
    results = cursor.fetchall()
    return json.dumps(results)

@eel.expose
def updateSetting(key, value):
    try:
        cursor.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))
        con.commit()
        return True
    except Exception as e:
        print(f"Settings Update Error: {e}")
        return False

# Assistant name
@eel.expose
def assistantName():
    name = ASSISTANT_NAME
    return name


@eel.expose
def personalInfo():
    try:
        cursor.execute("SELECT * FROM info")
        results = cursor.fetchall()
        jsonArr = json.dumps(results[0])
        eel.getData(jsonArr)
        return 1    
    except:
        print("no data")


@eel.expose
def updatePersonalInfo(name, designation, mobileno, email, city):
    cursor.execute("SELECT COUNT(*) FROM info")
    count = cursor.fetchone()[0]

    if count > 0:
        # Update existing record
        cursor.execute(
            '''UPDATE info 
               SET name=?, designation=?, mobileno=?, email=?, city=?''',
            (name, designation, mobileno, email, city)
        )
    else:
        # Insert new record if no data exists
        cursor.execute(
            '''INSERT INTO info (name, designation, mobileno, email, city) 
               VALUES (?, ?, ?, ?, ?)''',
            (name, designation, mobileno, email, city)
        )

    con.commit()
    personalInfo()
    return 1



@eel.expose
def displaySysCommand():
    cursor.execute("SELECT * FROM sys_command")
    results = cursor.fetchall()
    jsonArr = json.dumps(results)
    eel.displaySysCommand(jsonArr)
    return 1


@eel.expose
def deleteSysCommand(id):
    cursor.execute("DELETE FROM sys_command WHERE id = ?", (id,))
    con.commit()


@eel.expose
def addSysCommand(key, value):
    cursor.execute(
        '''INSERT INTO sys_command VALUES (?, ?, ?)''', (None,key, value))
    con.commit()


@eel.expose
def displayWebCommand():
    cursor.execute("SELECT * FROM web_command")
    results = cursor.fetchall()
    jsonArr = json.dumps(results)
    eel.displayWebCommand(jsonArr)
    return 1


@eel.expose
def addWebCommand(key, value):
    cursor.execute(
        '''INSERT INTO web_command VALUES (?, ?, ?)''', (None, key, value))
    con.commit()


@eel.expose
def deleteWebCommand(id):
    cursor.execute("DELETE FROM web_command WHERE Id = ?", (id,))
    con.commit()


@eel.expose
def displayPhoneBookCommand():
    cursor.execute("SELECT * FROM contacts")
    results = cursor.fetchall()
    jsonArr = json.dumps(results)
    eel.displayPhoneBookCommand(jsonArr)
    return 1


@eel.expose
def deletePhoneBookCommand(id):
    cursor.execute("DELETE FROM contacts WHERE Id = ?", (id,))
    con.commit()


@eel.expose
def InsertContacts(Name, MobileNo, Email, City):
    cursor.execute(
        '''INSERT INTO contacts VALUES (?, ?, ?, ?, ?)''', (None,Name, MobileNo, Email, City))
    con.commit()

def googleSearch(query):
    query = query.replace("google", "")
    query = query.strip()
    speak("Searching on Google: " + query)
    kit.search(query)

def tell_time(query):
    now = datetime.datetime.now()
    current_time = now.strftime("%I:%M %p")
    speak(f"The current time is {current_time}")

def open_and_write(query):
    try:
        if "write" in query:
             split_word = "write"
        elif "type" in query:
             split_word = "type"
        else:
             return
             
        parts = query.split(f" {split_word} ")
        if len(parts) < 2:
            return
            
        app_part = parts[0].replace("open", "").strip()
        content_part = parts[1].strip()
        
        speak(f"Opening {app_part}...")
        appopen(app_part, match_closest=True, output=False)
        time.sleep(3) 
        
        speak(f"Generating content for {content_part}...")
        
        offline_mode = get_setting_val('offline_mode')
        
        prompt = f"Write {content_part}. Do not include any conversational filler. Just the content."
        
        generated_text = ""
        if offline_mode == 'true' or not is_online():
             generated_text = offline_chat(prompt)
        else:
             generated_text = llama_chat(prompt)
             if not generated_text:
                 generated_text = offline_chat(prompt)
                 
        if generated_text:
             speak("Writing content now...")
             import pyperclip
             pyperclip.copy(generated_text)
             pyautogui.hotkey('ctrl', 'v')
             
             speak(f"I have written it in {app_part} sir.")
        else:
             speak("Sorry, I couldn't generate the content.")
             
    except Exception as e:
        print(f"OpenWrite Error: {e}")
    except Exception as e:
        print(f"OpenWrite Error: {e}")
        speak("I encountered an error doing that.")

# Advanced Features
import git
import ctypes
from yt_dlp import YoutubeDL

def git_push(query):
    try:
        query = query.replace("git push", "").strip()
        message = query if query else "Automated commit by Jarvis"
        
        # Assume current working directory is the repo or default to project path
        # Better: let user specify or use current CWD of execution if running from repo
        repo_path = os.getcwd() 
        speak(f"Pushing to git repository at {repo_path}")
        
        repo = git.Repo(repo_path)
        repo.git.add('.')
        repo.index.commit(message)
        origin = repo.remote(name='origin')
        origin.push()
        speak("Code pushed to repository successfully.")
    except Exception as e:
        print(f"Git Error: {e}")
        speak("Failed to push to git. Make sure this is a valid repository.")

def secure_download(query):
    # Pattern: "download [video/song] [query]"
    query = query.replace("download", "").strip()
    
    # Check for Youtube
    # Simple logic: assume it's a youtube search term if not a url
    speak(f"Searching and downloading {query}...")
    
    try:
        ydl_opts = {
            'format': 'best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
        }
        
        # We need to search first if it's not a URL
        if not query.startswith("http"):
            query = f"ytsearch1:{query}"
            
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info:
                filename = info['entries'][0]['title']
            else:
                filename = info['title']
                
        # Log to DB
        abs_path = os.path.join(os.getcwd(), 'downloads', filename)
        conn = sqlite3.connect("jarvis.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO downloads (filename, path) VALUES (?, ?)", (filename, abs_path))
        conn.commit()
        conn.close()
        
        speak(f"Downloaded {filename} successfully. Saved to secure downloads.")
        
    except Exception as e:
        print(f"Download Error: {e}")
        speak("Download failed.")

def system_lock():
    speak("Locking the system.")
    ctypes.windll.user32.LockWorkStation()