"""Read chat into data structures"""

from typing import List, Tuple
from math import ceil
import re
from collections import namedtuple
from datetime import datetime
import json
import yaml

MIN_CHUNK_SIZE = 10
MAX_CHUNK_SIZE = 200

Message = namedtuple(
    'Message', ['id', 'date', 'text', 'user', 'forward_date', 'forward_from', 'reply_to_id'],
)
MessagesChunk = namedtuple(
    'Message', ['messages', 'title'],
)

topics = None
topics_messages = None


def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat(sep=' ').replace('+00:00', '')
    raise TypeError(f"Type {type(obj)} not serializable")


# Дать номер недели
def get_week_number(date):
    if isinstance(date, str):
        from datetime import datetime
        date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
    return date.isocalendar()[1]


def count_words_and_punctuation_re(text: str) -> tuple[int, int]:
    # Находим все слова (последовательности букв/цифр)
    words = len(re.findall(r'\w+', text))

    # Находим все знаки препинания и спецсимволы
    punct = len(re.findall(r'[^\w\s]', text))

    return words, punct


def read_topic_names( filename ):
    with open( filename, 'r', encoding='utf-8' ) as file:
        return yaml.safe_load(file)


# Читаем файл с дампом сообщений
def read_chat_file( chat_dump_filename ):
    global topics, topics_messages

    with open( chat_dump_filename, 'r', encoding='utf-8' ) as file:
        tgmessages = json.load(file)

        topics_messages = {
            int(topic_id): [
                Message(*msg) for msg in messages
            ]
            for topic_id, messages in tgmessages['messages'].items()
        }

        topics = tgmessages['topics']

        del tgmessages

    return topics, topics_messages


# Поиск сообщения по его id в списке сообщений.
# Возвращает объект Message или None, если сообщение не найдено.
def get_msg_by_id( msg_id : int ):
    for messages in topics_messages.values():
        for msg in messages:
            if msg.id == msg_id:
                return msg
    return None


# Отформатировать цитируемое сообщение
def format_repliedto_msg(msg: Message) -> str:
    if not msg:
        return "> {Невозможно найти цитируемое сообщение}"

    header = f"> [{msg.date} from {msg.user}]"
    # Разбиваем текст на строки и добавляем символ цитирования к каждой
    quoted_text = '\n> '.join(msg.text.splitlines())

    return f"{header}\n> {quoted_text}\n"


# Форматирует сообщение в читаемый вид
def format_message( msg: Message, reply_info = True, fwd_info = True ) -> str:
    result = f"[{msg.date} from {msg.user}]"

    if msg.forward_from and reply_info:
        result += f" (переслано от {msg.forward_from} {msg.forward_date})"
    result += "\n"

    if msg.reply_to_id and fwd_info:
        replied_to_msg = get_msg_by_id( msg.reply_to_id )
        result += format_repliedto_msg( replied_to_msg )

    result += f"{msg.text}\n"
    return result


# Отформатировать все сообщения в чате
def format_all_messages( messages: List[Tuple], reply_info = True, fwd_info = True ) -> str:
    result = "Содержимое чата:\n"
    result += "****\n\n".join([
        format_message( msg, reply_info, fwd_info ) for msg in messages
    ])
    return result


# Собрать в один список все сообщения в чате (только в топиках only_topic_ids)
def gather_all_messages_from_all_topics( only_topic_ids : List[int] = [] ) -> List[Message]:
    all_messages = []
    if only_topic_ids:
        for topic_id in only_topic_ids:
            if topic_id in topics_messages:
                all_messages += topics_messages[topic_id]
    else:
        for messages in topics_messages.values():
            all_messages += messages

    return all_messages


# Разделить список сообщений на чанки
# Разбиения списка сообщений телеграм-чата на чанки.
# split_mode == 'msgcnt' — режим разбиения по количеству сообщений (не более max_chunk_size).
# split_mode = 'smartweek' — smart-режим по неделям, который должен работал так:
# если собщений менее max_chunk_size — вообще не делил бы на чанки,
# если собщений более max_chunk_size, то тогда делил бы по неделям (по topic_message.date),
# ОДНАКО если в какой-то неделе слишком мало сообщений (менее MIN_CHUNK_SIZE),
# то он бы объединял бы список сообщений с соседними (следующими) неделями, пока мы не превысим MIN_CHUNK_SIZE.
# При этом в этом новом режиме split_mode = 'smartweek' у MessagesChunk должен выставляться title = 'W{weeknum}',
# где weeknum — номер недели (считается от начала года).
# А если недели объединяются, то тогда title выглядел бы как 'W1W3W5',
# где W{weeknum} — неделя с определённым номером, из которой сообщения объединены.
# Если в какой-то неделе сообщений вообще нет, то тогда не этой недели с её номером вообще нет в title.
def split_messages_into_chunks(
    topic_messages: list[Message], split_mode = 'msg_cnt', # smartweek
    max_chunk_size: int = MAX_CHUNK_SIZE
) -> list[tuple]:
    if not topic_messages:
        return None
    msg_cnt = len(topic_messages)

    if msg_cnt <= max_chunk_size:
        # Если сообщений меньше max_chunk_size, создаем один чанк
        chunk = MessagesChunk( topic_messages, '' )
        return [chunk]

    if split_mode == 'msg_cnt': # Слайсинг по количеству сообщений
        # Вычисляем количество чанков и их размер
        chunk_count = ceil(msg_cnt / max_chunk_size)
        chunk_size = ceil(msg_cnt / chunk_count)
        chunks = []

        # Разбиваем сообщения на чанки
        for chunk_num, i in enumerate( range(0, msg_cnt, chunk_size) ):
            chunk_messages = topic_messages[ i:i + chunk_size ]
            chunk = MessagesChunk( chunk_messages, str(chunk_num), )
            chunks.append( chunk )

        return chunks

    elif split_mode == 'smartweek': # Слайсинг по неделям
        # Группируем сообщения по неделям
        weeks_dict = {}
        for msg in topic_messages:
            week_num = get_week_number(msg.date)
            if week_num not in weeks_dict:
                weeks_dict[week_num] = []
            weeks_dict[week_num].append(msg)

        # Сортируем недели
        sorted_weeks = sorted( weeks_dict.items(), key=lambda x: x[0] )

        chunks = []
        current_chunk = []
        current_weeks = []

        for week_num, messages in sorted_weeks:
            current_chunk.extend(messages)
            current_weeks.append(week_num)
            
            # Если размер текущего чанка достиг MIN_CHUNK_SIZE, проверяем нужно ли его сохранять
            if len(current_chunk) >= MIN_CHUNK_SIZE:
                title = ''.join([f'W{w}' for w in current_weeks])
                chunk = MessagesChunk( current_chunk, title )
                chunks.append(chunk)
                current_chunk = []
                current_weeks = []
        
        # Добавляем оставшиеся сообщения, если есть
        if current_chunk:
            title = ''.join([f'W{w}' for w in current_weeks])
            chunk = MessagesChunk( current_chunk, title )
            chunks.append(chunk)
            
        return chunks
    else:
        raise ValueError(f"Unknown split_mode: {split_mode}")
