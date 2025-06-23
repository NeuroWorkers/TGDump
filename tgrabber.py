#!/usr/bin/env python3
import asyncio
import os
import json
import telethon.sessions
from datetime import datetime
from telethon import TelegramClient
from chatdata import Message

from telethon.tl.functions.channels import GetForumTopicsRequest
from telethon.tl.types import (
    MessageService, DocumentAttributeVideo, DocumentAttributeAudio,
    DocumentAttributeFilename, Channel, User
)

from configs.telegram_config import (
    API_ID, API_HASH, SESSION_STRING,
    group_username, media_dir_parth, last_dump_file
)


def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat(sep=' ').replace('+00:00', '')
    raise TypeError(f"[ERROR] Ошибка сериализации {type(obj)}")


def make_user_string(peer):
    if not peer:
        return None

    username = getattr(peer, 'username', '')
    title = ''
    if isinstance(peer, User):
        title = ' '.join(filter(None, [peer.first_name, peer.last_name]))
    elif isinstance(peer, Channel):
        title = peer.title
    else:
        raise Exception(f'[ERROR] Неизвестный пир: {peer}')

    return f"@{username} ({title})" if username else title or f"id:{peer.id}"


def get_attr(document, attr_type):
    return next((a for a in document.attributes if isinstance(a, attr_type)), None)


def get_file_name(document):
    attr = get_attr(document, DocumentAttributeFilename)
    return attr.file_name if attr else 'unknown'


def get_duration(document):
    attr = get_attr(document, DocumentAttributeVideo) or get_attr(document, DocumentAttributeAudio)
    return getattr(attr, 'duration', 'unknown')


async def save_media(client, message, folder=media_dir_parth):
    os.makedirs(folder, exist_ok=True)
    if not message.media:
        return None
    try:
        path = await client.download_media(message.media, file=folder)
        return path
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки сообщения с id - {message.id}: {e}")
        return None


async def extract_message_data(message, client):
    reply_to_id = None
    topic_id = None
    media_info = {}

    if message.reply_to:
        r = message.reply_to
        if r.forum_topic:
            topic_id = r.reply_to_top_id or r.reply_to_msg_id
            reply_to_id = r.reply_to_msg_id
        else:
            reply_to_id = r.reply_to_msg_id

    topic_id = int(topic_id or 1)


    original_text = message.text or ""

    if message.media:
        path = await save_media(client, message)
        media_type = message.media.__class__.__name__.lower()

        media_info = {
            'type': media_type,
            'path': path,
        }

        document = getattr(message, 'document', None)
        if document:
            file_name = get_file_name(document)
            duration = get_duration(document)
            media_info.update({
                'file_name': file_name,
                'duration': duration,
                'mime_type': getattr(document, 'mime_type', 'unknown'),
                'size': getattr(document, 'size', None),
            })

        if 'photo' in media_type:
            caption = f"[ФОТО сохранено по адресу {path}]"
        elif 'video' in media_type:
            caption = f"[ВИДЕО сохранено по адресу {path}]"
        elif 'audio' in media_type:
            caption = f"[АУДИО сохранено по адресу {path}]"
        elif 'voice' in media_type:
            caption = f"[ГОЛОСОВОЕ сохранено по адресу {path}]"
        elif 'sticker' in media_type:
            caption = f"[СТИКЕР сохранен по адресу {path}]"
        else:
            caption = f"[{media_type.upper()} saved to {path}]"

        if original_text:
            text = f"{original_text}\n\n{caption}"
        else:
            text = caption
    else:
        text = original_text

    sender = await message.get_sender()
    fwd_sender = None
    fwd_date = None
    if message.fwd_from:
        fwd_date = message.fwd_from.date
        fwd_sender = message.fwd_from.from_name or None
        if not fwd_sender and message.fwd_from.from_id:
            try:
                ent = await client.get_entity(message.fwd_from.from_id)
                fwd_sender = make_user_string(ent)
            except Exception:
                fwd_sender = None

    msg = Message(
        message.id, message.date, text,
        make_user_string(sender),
        fwd_date, fwd_sender, reply_to_id
    )

    return topic_id, {'Загруженный текст': msg, 'Загруженное медиа': media_info or None}


def load_last_dump_date(filename=last_dump_file):
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            date_str = f.read().strip()
            if date_str:
                return datetime.fromisoformat(date_str)
    except Exception as e:
        print(f"[WARNING] Невозможно прочитать дату последнего дампа!: {e}")
    return None


def save_last_dump_date(date, filename=last_dump_file):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(date.isoformat())
    except Exception as e:
        print(f"[WARNING] Невозможно сохранить дату последнего дампа!: {e}")


async def main():
    session = telethon.sessions.StringSession(SESSION_STRING)
    client = TelegramClient(session, API_ID, API_HASH)
    await client.start()
    print("Запущен дамп телеграм топика!")

    group = await client.get_entity(group_username)
    print(f"Группа: {group.title}")

    topics_resp = await client(GetForumTopicsRequest(
        channel=group, offset_date=0, offset_id=0, offset_topic=0, limit=100
    ))
    topic_ids = {t.id for t in topics_resp.topics}
    topic_messages = {}
    topics = [(t.id, t.title) for t in topics_resp.topics]

    last_dump_date = load_last_dump_date()
    print(f"Дата последнего дампа: {last_dump_date}")

    newest_date = last_dump_date

    async for message in client.iter_messages(group, reverse=True):
        if isinstance(message, MessageService):
            continue

        if last_dump_date and message.date <= last_dump_date:
            continue

        topic_id, entry = await extract_message_data(message, client)
        if not entry:
            continue

        topic_messages.setdefault(topic_id, []).append(entry)

        if newest_date is None or message.date > newest_date:
            newest_date = message.date

        print('.', end='', flush=True)

    print("\nСтатистика топика:")
    for tid, msgs in topic_messages.items():
        print(f"В топике - {tid}: {len(msgs)} сообщений(-я)")

        with open(f"../messages/file_{tid}.txt", "w", encoding="utf-8") as f:
            json.dump({"messages": topic_messages},
                      f, ensure_ascii=False, indent=4, default=json_serial)

    if newest_date:
        save_last_dump_date(newest_date)

    await client.disconnect()


asyncio.run(main())