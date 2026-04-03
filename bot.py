from datetime import date, datetime, timezone, timedelta
import email
import os
import sys
import time

import atproto
import feedparser
import requests

DB_FILE_PATH = "pubdb.txt"

# currently (Feb 2025) this feed (and all arxiv feeds?) don't update on the weekends. they update Sunday-Thursday night I think
# TODO: drop to 3 days?
NUM_DAYS_RETAIN = 7

def read_db(db_path):
    if not os.path.exists(db_path):
        return set()
    with open(db_path, 'r') as f:
        lines = f.readlines()
    now = datetime.now(tz=timezone.utc)
    retain_limit = now - timedelta(days=NUM_DAYS_RETAIN)
    db = set()
    for line in lines:
        guid, published_str = line.strip().split('\t')
        pub_date = datetime.fromisoformat(published_str)
        # if entry is older than N days, remove from database
        if retain_limit <= pub_date:
            db.add((guid, pub_date))
    return db

def write_db(db_path, db):
    db = list(db)
    db.sort()
    with open(db_path, 'w') as f:
        for guid, published in db:
            f.write(f"{guid}\t{published}\n")

def format_post(title, link):
    post_str = f"{title}\n{link}"
    return post_str

def make_posts(paper_infos, delay_secs=2):
    client = atproto.Client()
    handle = os.environ["BSKY_HANDLE"]
    password = os.environ["BSKY_PASS"]
    client.login(handle, password)
    for paper in paper_infos:
        text_builder = atproto.client_utils.TextBuilder()
        text_builder.text(f"{paper['title']}\n")
        text_builder.link(paper['link'], paper['link'])
        result = client.send_post(text_builder)
        print(f"Posted to: {result.uri}")
        time.sleep(delay_secs)

def apply_bot_label():
    from atproto import models
    client = atproto.Client()
    client.login(os.environ["BSKY_HANDLE"], os.environ["BSKY_PASS"])
    repo_record = client.com.atproto.repo.get_record({
        'collection': models.ids.AppBskyActorProfile,
        'repo': client.me.did,
        'rkey': 'self'
    }).value
    client.com.atproto.repo.put_record(models.ComAtprotoRepoPutRecord.Data(
        collection=models.ids.AppBskyActorProfile,
        repo=client.me.did,
        rkey='self',
        record=models.AppBskyActorProfile.Record(
            display_name=repo_record.display_name,
            description=repo_record.description,
            avatar=repo_record.avatar, # This is now a BlobRef, not a string
            banner=repo_record.banner, # This is now a BlobRef, not a string
            labels=models.ComAtprotoLabelDefs.SelfLabels(
                values=[models.ComAtprotoLabelDefs.SelfLabel(val='bot')]
            )
        )
    ))
    print("Bot label applied successfully.")


def run():
    if len(sys.argv) != 2:
        print("Usage: python bot.py <subject string>")
        sys.exit(1)

    subject = sys.argv[1]
    rss_url = f"https://rss.arxiv.org/rss/{subject}"
    response = requests.get(rss_url)

    apply_bot_label()

    feed = feedparser.parse(response.content)
    if feed.bozo:
        print(f"Error parsing the feed for subject '{subject}'.")
        sys.exit(1)

    db = read_db(DB_FILE_PATH)
    now = datetime.now(timezone.utc)
    paper_infos = []
    for entry in feed.entries:
        guid = entry.get('guid', '')
        published_str = entry.get('published', '')
        pub_date = email.utils.parsedate_to_datetime(published_str)
        if pub_date.tzinfo is None:
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        else:
            pub_date = pub_date.astimezone(timezone.utc)
        db_entry = (guid, pub_date)
        if db_entry in db:
            continue
        author = entry.get('author', '')
        title = entry.get('title', '')
        link = entry.get('link', '')
        paper_infos.append({ 'title': title, 'link': link })
        db.add(db_entry)

    make_posts(paper_infos)

    write_db(DB_FILE_PATH, db)


if __name__ == '__main__':
    run()
