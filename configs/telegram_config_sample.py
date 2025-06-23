import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))

API_ID = 0
API_HASH = ''
SESSION_STRING = ''

group_username = ''

output_filename = os.path.join(BASE_DIR, "tg_fetcher", "downloaded_text", "messages.json")
output_dir = os.path.join(BASE_DIR, "tg_fetcher", "downloaded_text")
media_dir_parth = os.path.join(BASE_DIR, "tg_fetcher", "downloaded_media")
last_dump_file = os.path.join(BASE_DIR, "tg_fetcher", "last_dump", "last_dump_date.txt")

specific_topic_id = 1275
