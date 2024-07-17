import pixabay.core
import textwrap
import time
import ssl
import google.generativeai as genai
from googleapiclient.http import MediaFileUpload
import datetime
from bark import SAMPLE_RATE, generate_audio, preload_models
from moviepy.editor import *
from scipy.io.wavfile import write as write_wav
from IPython.display import Markdown
from PIL import Image, ImageDraw
from Google import Create_Service
import os


def to_markdown(text):
    text = text.replace('•', '  *')
    return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))


GOOGLE_API_KEY = 'AIzaSyBJnUId-rXU9CwLgJOpgI0DaXb6UuLLEns'
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

px = pixabay.core("44790067-3e1f2ed78608e912fc554b2de")

CLIENT_SECRET_FILE = 'client-secrets.json'
API_NAME = 'youtube'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)
upload_date_time = datetime.datetime(2024, 7, 17, 7, 56, 0).isoformat() + '.000Z'
not_uploaded = True


def generate_script(topic):
    response = model.generate_content(f'''You are the "history of" youtube channel and make engaging video about the history of different ideas and topics.
    Can you write an informative script (and a clickable title that is optimised for keywords and starts with 'history of'. NO EMOJIS!)
   about the history of {topic} in the following format:
  (repeat the shot and narrator parts as many times as you want. MAKE THE SCRIPT TAKE AT LEAST 2800 WORDS):

  ## Title: title that you made (starting with - 'the history of'

  ## Description: Description that you made, optimised for keywords on youtube

  **[Shot:]** What you think the video should be behind the script. Note: I will be using theses to search the pixabay API so keep them simple one word queries. I will be choosing the first one from the result so make your query specific. 

  **NARRATOR:** The script that you would like to be said over the video. PLEASE MAKE SURE THAT THERE IS ONLY ONE SPACE AFTER **NARRATOR**

  Please dont use emojis! The first shot query will be used for the thumbnail so make it important.
  ''')
    to_markdown(response.text)
    for chunk in response:
        with open('script.txt', 'w') as file:
            file.write(f"{chunk.text}\n")


MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:


with information from the API Console
https://console.cloud.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
"""


def generate_lines():
    preload_models()
    with open('script.txt', 'r') as script, open('lines.txt', 'w') as audio_lines:
        for line in script:
            if "**NARRATOR:**" in line:
                audio_lines.write(line.replace("**NARRATOR:** ", ""))
    line_number = 1
    with open('lines.txt', 'r') as text_lines:
        for line in text_lines:
            generate_bark_speech(line, f"Script_{line_number}")
            print(f"Audio {line_number} completed saying {line}")
            line_number += 1


def send_to_youtube(filename, title, description):
    print(f"Starting to upload {filename} to platforms...")
    request_body = {
        'snippet': {
            'categoryI': 19,
            'title': title,
            'description': description,
            'tags': ['History', 'Information', 'Learning']
        },
        'status': {
            'privacyStatus': 'public',
            'publishAt': upload_date_time,
            'selfDeclaredMadeForKids': False,
        },
        'notifySubscribers': True
    }
    media_file = MediaFileUpload(filename)
    print("Going OK, just a few moments...")
    response_upload = service.videos().insert(
        part='snippet,status',
        body=request_body,
        media_body=media_file
    ).execute()
    print("Just the thumbnail left!")
    service.thumbnails().set(
        videoId=response_upload.get('id'),
        media_body=MediaFileUpload('thumbnail.png')
    ).execute()
    print(f"Now theres has a new video: {title}!")
    not_uploaded = False


def generate_bark_speech(line, name):
    audio_array = generate_audio(line.rstrip())
    write_wav(f"{name.rstrip()}.wav", SAMPLE_RATE, audio_array)


def create_image_with_text(text):
    query = px.query(text)
    query[0].download("thumbnail.png", "largeImage")


def generate_shots():
    with open('script.txt', 'r') as script, open("shots.txt", 'w') as shots:
        for line in script:
            if "**[Shot:]**" in line:
                shots.write(line.replace("**[Shot:]**", ""))
    line_number = 1
    with open("shots.txt", 'r') as shots:
        for line in shots:
            get_video_from_keywords_api(line.rstrip(), line_number)
            line_number += 1


def get_video_from_keywords_api(keyword, number):
    try:
        not_right = True
        media = px.queryVideo(keyword)
        name = keyword.split(" ")
        name = "_".join(name)
        try_no = 0
        while not_right:
            media[try_no].download("video_{}.mp4".format(name), "large")
            check_clip = VideoFileClip(f"video_{name}.mp4")
            width, height = check_clip.size
            if width == 1920 and height == 1080:
                not_right = False
            else:
                os.remove(f"video_{name}.mp4")
                print(f"Not the correct size for {keyword}")
                try_no += 1
        video_clip = VideoFileClip(F"video_{name}.mp4")
        new_clip = video_clip.without_audio()
        new_clip.write_videofile(f"shot_{number}.mp4")
    except Exception as e:
        generate_backup_keyword(keyword, number)


def generate_backup_keyword(failed, failed_no):
    response = model.generate_content(f'''
    You have generated a keyword to use in the pixabay API that failed to return any results.
    This keyword is {failed}. Could you generate a simular keyword that would return results?
    Return a single word and make sure that single word won't return the {failed} if put in this very prompt.
      ''')
    to_markdown(response.text)
    for chunk in response:
        with open('backup.txt', 'w') as file:
            file.write(f"{chunk.text}\n")
    print(f"{failed} failed")
    with open("backup.txt", "r") as keyword:
        for line in keyword:
            get_video_from_keywords_api(line.rstrip(), failed_no)
            break


def loop_video_to_audio_duration(video_path, audio_path, output_path):
    try:
        # Verify if the files exist
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        # Load the audio file using moviepy
        print("Loading audio file...")
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        print(f"Audio duration: {audio_duration} seconds")
        # Load the video file using moviepy
        print("Loading video file...")
        video_clip = VideoFileClip(video_path)
        video_duration = video_clip.duration
        print(f"Video duration: {video_duration} seconds")
        # Calculate how many times to loop the video
        num_loops = int((audio_duration / video_duration) + 1)
        print(f"Number of loops needed: {num_loops}")
        # Create a list of the looped video clips and concatenate them
        print("Concatenating video clips...")
        looped_clips = [video_clip] * num_loops
        looped_video = concatenate_videoclips(looped_clips)
        looped_video = looped_video.subclip(0, audio_duration)
        print("Looped video created.")
        # Set the audio to the video
        print("Setting audio to video...")
        final_video = looped_video.set_audio(audio_clip)
        # Write the output file
        print("Writing final video file...")
        final_video.write_videofile(output_path, codec="libx264", fps=24, audio_codec="aac")
        print("Final video created successfully.")
    except FileNotFoundError as fnf_error:
        print(fnf_error)
    except Exception as e:
        print(f"An error occurred: {e}")


def combine_audio_video():
    with open('lines.txt', 'r') as lines:
        number = 1
        for line in lines:
            video_path = os.path.abspath(f"shot_{number}.mp4")
            audio_path = f"Script_{number}.wav"
            output_path = os.path.abspath(f"Final_{number}.mp4")
            loop_video_to_audio_duration(video_path, audio_path, output_path)
            number += 1


def check_for_audio():
    number = 1
    if not os.path.isfile(f'Script_{number}.wav'):
        print("Audio file not found!")
        return
    else:
        print("Found it!")


def concatenate_videos(input_videos, output_name):
    clips = [VideoFileClip(video) for video in input_videos]
    final_clip = concatenate_videoclips(clips)
    final_clip.write_videofile(output_name)
    return


def final_combine(ideas):
    videos_list = []
    number = 1
    with open("shots.txt", 'r') as counter:
        for line in counter:
            videos_list += [f'Final_{number}.mp4']
            number += 1
    name = ideas.split(" ")
    name = "_".join(name)
    concatenate_videos(videos_list, f'{name}.mp4')
    upload(f'{name}.mp4')
    return


def clean_up():
    with open('lines.txt', 'r') as counting:
        current = 0
        for line in counting:
            current += 1
            try:
                print(f"removing temporary files for generation: {current}")
                os.remove(f"Script_{current}.wav")
                os.remove(f"shot_{current}.mp4")
                os.remove(f"Final_{current}.mp4")
            except Exception as e:
                print(e)


def upload(filename):
    with open('script.txt', 'r') as data:
        title = ''
        description = ''
        for line in data:
            if "## Title:" in line:
                title = line.replace("## Title: ", "")
            elif "## Description:" in line:
                description = line.replace("## Description:", "")
            elif "**[Shot:]**" in line:
                shot = line.replace("**[Shot:]**", "")
                create_image_with_text(shot.rstrip())
                break
        while not_uploaded:
            try:
                send_to_youtube(filename, title.rstrip(), description.rstrip())
            except TimeoutError:
                print("Failed to upload video. Check your network connection. Retrying in 5 seconds...")
                time.sleep(5)
            except ssl.SSLWantWriteError:
                print("The write operation did not complete. Retrying in 5 seconds...")
                time.sleep(5)


#idea = input("I will write a script about ")
#generate_script(idea)
#print(f"Script generated about {idea}")
#generate_lines()
#generate_shots()
#combine_audio_video()
#final_combine(idea)
upload("guitars.mp4")
clean_up()
print("Done.")
# final steps is to test the uploading code. I think a shorts generator would be good to extend to multiple platforms
