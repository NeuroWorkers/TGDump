import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))

API_ID = 0
API_HASH = ''
SESSION_STRING = ''

group_username = ''

output_dir = os.path.join(BASE_DIR, "tg_fetcher")
output_dir_text = os.path.join(output_dir, "downloaded_text")
output_filename = os.path.join(output_dir, "downloaded_text", "messages.json")
media_dir_parth = os.path.join(output_dir, "downloaded_media")
last_dump_file = os.path.join(output_dir, "last_dump_date.txt")

specific_topic_id = 1275
