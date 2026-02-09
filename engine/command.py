import pyttsx3
import speech_recognition as sr
import eel
import time
import os
import sqlite3
from gtts import gTTS
import pygame
import requests
import keyboard      
import threading

# Global variables for speech control
stop_speaking_flag = False

def init_hotkey():
    keyboard.add_hotkey('F6', stop_speech)
    print("Hotkey F6 registered for stopping speech.")

def stop_speech():
    global stop_speaking_flag
    print("Stop Hotkey Pressed!")
    stop_speaking_flag = True
    try:
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
    except:
        pass
    
    try:
        # For pyttsx3, it's harder to interupt mid-utterance if blocking
        # But we can try to re-init or just rely on the loop check
        pass 
    except:
        pass

def is_online():
    try:
        requests.get('https://www.google.com', timeout=3)
        return True
    except:
        return False

def get_setting(key):
    try:
        con = sqlite3.connect("jarvis.db")
        cursor = con.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = cursor.fetchone()
        con.close()
        return result[0] if result else None
    except:
        return None

def speak(text):
    global stop_speaking_flag
    stop_speaking_flag = False # Reset flag at start
    text = str(text)
    
    language = get_setting('preferred_language') or 'en'
    
    if language == 'en' or not is_online():
        try:
            # We will use running the loop in a way that checks?
            # pyttsx3 runAndWait blocks.
            # To interrupt, we might need to split text or run in thread.
            # Simple approach: Check flag before starting.
            # If we really want instant interrupt for pyttsx3, we need to use 'connect' to callbacks
            # and stop loop.
            
            engine = pyttsx3.init('sapi5')
            voices = engine.getProperty('voices') 
            engine.setProperty('voice', voices[0].id)
            engine.setProperty('rate', 174)
            eel.DisplayMessage(text)
            engine.say(text)
            eel.receiverText(text)
            
            # This blocks. To support interruption, we'd need more complex logic.
            # But for gTTS (Indian languages) we can interrupt easily.
            # For English, let's keep it simple for now or try to check flag?
            # Actually, keyboard hook runs in thread, so we can stop engine.
            
            def onWord(name, location, length):
               if stop_speaking_flag:
                   engine.stop()
                   
            engine.connect('started-word', onWord)
            engine.runAndWait()
        except:
             print("pyttsx3 error")

    else:
        try:
            eel.DisplayMessage(text)
            eel.receiverText(text)
            
            tts = gTTS(text=text, lang=language)
            filename = "voice.mp3"
            if os.path.exists(filename):
                os.remove(filename)
                
            tts.save(filename)
            
            pygame.mixer.init()
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            
            while pygame.mixer.music.get_busy():
                if stop_speaking_flag:
                    pygame.mixer.music.stop()
                    break
                pygame.time.Clock().tick(10)
                
            pygame.mixer.music.unload()
            try:
                os.remove(filename)
            except:
                pass
        except Exception as e:
            print(f"gTTS failed: {e}")
            engine = pyttsx3.init('sapi5')
            engine.say(text)
            engine.runAndWait()

# Initialize Hotkey
try:
   init_hotkey()
except Exception as e:
   print(f"Hotkey init failed: {e}")

def takecommand():
    r = sr.Recognizer()

    with sr.Microphone() as source:
        print('listening....')
        eel.DisplayMessage('listening....')
        r.pause_threshold = 1.5 # Adjusted for finding controls
        r.adjust_for_ambient_noise(source)
        
        try:
            # Removed phrase_time_limit to listen until silence (based on pause_threshold)
            # Timeout is strictly for waiting for speech to START.
            audio = r.listen(source, timeout=10)
        except:
            return ""

    try:
        print('recognizing')
        eel.DisplayMessage('recognizing....')
        
        language = get_setting('preferred_language') or 'en'
        
        # Simple mapping for common Indian languages to Google Speech codes
        lang_map = {
            'en': 'en-in',
            'hi': 'hi-IN',
            'ta': 'ta-IN',
            'te': 'te-IN',
            'kn': 'kn-IN',
            'ml': 'ml-IN',
            'mr': 'mr-IN',
            'gu': 'gu-IN',
            'bn': 'bn-IN'
        }
        lang_code = lang_map.get(language, 'en-in')
        
        query = r.recognize_google(audio, language=lang_code)
        print(f"user said: {query}")
        eel.DisplayMessage(query)
       
    except Exception as e:
        print(e)
        return ""
    
    return query.lower()

@eel.expose
def allCommands(message=1):

    if message == 1:
        query = takecommand()
        print(query)
        eel.senderText(query)
    else:
        query = message
        eel.senderText(query)
    try:

        if "open" in query and ("write" in query or "type" in query):
            from engine.features import open_and_write
            open_and_write(query)
            
        elif "open" in query:
            from engine.features import openCommand
            openCommand(query)
            
        elif "time" in query:
            from engine.features import tell_time
            tell_time(query)
            
        elif "google" in query:
            from engine.features import googleSearch
            googleSearch(query)

        elif "git push" in query:
            from engine.features import git_push
            git_push(query)
            
        elif "download" in query:
             from engine.features import secure_download
             secure_download(query)
             
        elif "lock system" in query or "secure system" in query:
             from engine.features import system_lock
             system_lock()

        elif "on youtube" in query:
            from engine.features import PlayYoutube
            PlayYoutube(query)
        
        elif "send message" in query or "phone call" in query or "video call" in query:
            from engine.features import findContact, whatsApp, makeCall, sendMessage
            contact_no, name = findContact(query)
            if(contact_no != 0):
                speak("Which mode you want to use whatsapp or mobile")
                preferance = takecommand()
                print(preferance)

                if "mobile" in preferance:
                    if "send message" in query or "send sms" in query: 
                        speak("what message to send")
                        message = takecommand()
                        sendMessage(message, contact_no, name)
                    elif "phone call" in query:
                        makeCall(name, contact_no)
                    else:
                        speak("please try again")
                elif "whatsapp" in preferance:
                    message = ""
                    if "send message" in query:
                        message = 'message'
                        speak("what message to send")
                        query = takecommand()
                                        
                    elif "phone call" in query:
                        message = 'call'
                    else:
                        message = 'video call'
                                        
                    whatsApp(contact_no, query, message, name)
        
        else:
            # Check ChatBot Mode Setting
            chat_mode = get_setting('chat_mode')
            # Default to true if not set, or check string 'true'
            if chat_mode == 'false':
                 speak("ChatBot mode is disabled. Command not recognized.")
            else:
                 from engine.features import chatBot
                 chatBot(query)
    except Exception as e:
        print(f"error: {e}")
    
    eel.ShowHood()