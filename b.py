import requests
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

token = "user-token"
target_id = "target-id" 

# configure what to delete [set True to enable, False to disable each type]
delete_config = {
    "images": True,      # jpg, jpeg, png, gif ..
    "videos": False,      # mp4, mov ...
    "audio": False,      # mp3, wav, ogg ..
    "voice": False,      # voice messages
    "messages": True    # text messages
}

headers = {
    'authorization': token,
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

base_url = "https://discord.com/api/v9"
max_workers = 5
image_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.ico')
video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v')
audio_exts = ('.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus', '.wma', '.aiff', '.ape')

def getuserinfo():
    resp = requests.get(f"{base_url}/users/@me", headers=headers)
    if resp.status_code == 200:
        return resp.json()
    raise Exception("invalid token")

def checkdm(userid):
    resp = requests.post(f"{base_url}/users/@me/channels", headers=headers, json={"recipient_id": userid})
    if resp.status_code == 200:
        return resp.json()['id']
    return None

def checkchannel(channelid):
    resp = requests.get(f"{base_url}/channels/{channelid}", headers=headers)
    if resp.status_code == 200:
        return resp.json()
    return None

def checkguild(guildid):
    resp = requests.get(f"{base_url}/guilds/{guildid}", headers=headers)
    if resp.status_code == 200:
        return resp.json()['name']
    return None

def resolvetarget(targetid):
    channel = checkchannel(targetid)
    if channel and channel.get('type') in (1, 3):
        recipients = channel.get('recipients', [])
        if recipients:
            targetname = ", ".join(user.get('username', 'unknown') for user in recipients)
        else:
            targetname = "dm"
        return {
            'channel_id': channel['id'],
            'target_name': f"dm with {targetname}",
            'target_type': 'dm'
        }

    dmchannel = checkdm(targetid)
    if dmchannel:
        user = checkchannel(dmchannel)
        recipients = user.get('recipients', []) if user else []
        if recipients:
            targetname = ", ".join(member.get('username', 'unknown') for member in recipients)
        else:
            targetname = "dm"
        return {
            'channel_id': dmchannel,
            'target_name': f"dm with {targetname}",
            'target_type': 'dm'
        }

    guildname = checkguild(targetid)
    if guildname:
        return {
            'channel_id': None,
            'target_name': guildname,
            'target_type': 'guild'
        }

    return None

def searchmedia(channelid, authorid, offset=0):
    if channelid:
        url = f"{base_url}/channels/{channelid}/messages/search"
        params = {
            'author_id': authorid,
            'has': 'file',
            'offset': offset
        }
    else:
        url = f"{base_url}/guilds/{target_id}/messages/search"
        params = {
            'author_id': authorid,
            'has': 'file',
            'include_nsfw': 'true',
            'offset': offset
        }
    
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 429:
        retry = resp.json().get('retry_after', 5)
        time.sleep(retry)
        return searchmedia(channelid, authorid, offset)
    return None

def searchvoice(channelid, authorid, offset=0):
    if channelid:
        url = f"{base_url}/channels/{channelid}/messages/search"
        params = {
            'author_id': authorid,
            'has': 'sound',
            'offset': offset
        }
    else:
        url = f"{base_url}/guilds/{target_id}/messages/search"
        params = {
            'author_id': authorid,
            'has': 'sound',
            'include_nsfw': 'true',
            'offset': offset
        }
    
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 429:
        retry = resp.json().get('retry_after', 5)
        time.sleep(retry)
        return searchvoice(channelid, authorid, offset)
    return None

def searchmessages(channelid, authorid, offset=0):
    if channelid:
        url = f"{base_url}/channels/{channelid}/messages/search"
        params = {
            'author_id': authorid,
            'offset': offset
        }
    else:
        url = f"{base_url}/guilds/{target_id}/messages/search"
        params = {
            'author_id': authorid,
            'include_nsfw': 'true',
            'offset': offset
        }
    
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 429:
        retry = resp.json().get('retry_after', 5)
        time.sleep(retry)
        return searchmessages(channelid, authorid, offset)
    return None

def deletemsg(channelid, msgid):
    url = f"{base_url}/channels/{channelid}/messages/{msgid}"
    resp = requests.delete(url, headers=headers)
    if resp.status_code == 429:
        retry = resp.json().get('retry_after', 1)
        time.sleep(retry)
        return deletemsg(channelid, msgid)
    return resp.status_code == 204

def shoulddelete(attachments):
    for att in attachments:
        filename = att.get('filename', '').lower()
        contenttype = att.get('content_type', '')
        if delete_config['images']:
            if contenttype.startswith('image/') or filename.endswith(image_exts):
                return True
        if delete_config['videos']:
            if contenttype.startswith('video/') or filename.endswith(video_exts):
                return True
        if delete_config['audio']:
            if contenttype.startswith('audio/') or filename.endswith(audio_exts):
                return True
    return False

def processfiles(channelid, userid):
    deleted = 0
    offset = 0
    while True:
        result = searchmedia(channelid, userid, offset)
        if not result:
            break
        messages = result.get('messages', [])
        if not messages:
            break
        batch = []
        
        for msggroup in messages:
            if isinstance(msggroup, list) and len(msggroup) > 0:
                msg = msggroup[0]
            else:
                continue
            attachments = msg.get('attachments', [])
            if not attachments or not shoulddelete(attachments):
                continue
            
            channelid_msg = msg.get('channel_id')
            msgid = msg.get('id')
            timestamp = msg.get('timestamp', '')
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestr = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    timestr = timestamp[:10]
            else:
                timestr = "unknown"
            
            batch.append({
                'channel_id': channelid_msg,
                'message_id': msgid,
                'timestamp': timestr
            })
        
        if batch:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for item in batch:
                    future = executor.submit(deletemsg, item['channel_id'], item['message_id'])
                    futures.append((future, item))
                for future, item in futures:
                    if future.result():
                        deleted += 1
                        if deleted % 10 == 0 or deleted == 1:
                            print(f"deleted [{deleted}] media ({item['timestamp']})")
            
            time.sleep(0.1)
        offset += 25
    return deleted

def processvoice(channelid, userid):
    deleted = 0
    offset = 0
    
    while True:
        result = searchvoice(channelid, userid, offset)
        if not result:
            break
        messages = result.get('messages', [])
        if not messages:
            break
        batch = []
        for msggroup in messages:
            if isinstance(msggroup, list) and len(msggroup) > 0:
                msg = msggroup[0]
            else:
                continue
            attachments = msg.get('attachments', [])
            if not attachments:
                continue
            channelid_msg = msg.get('channel_id')
            msgid = msg.get('id')
            timestamp = msg.get('timestamp', '')
            
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestr = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    timestr = timestamp[:10]
            else:
                timestr = "unknown"
            
            batch.append({
                'channel_id': channelid_msg,
                'message_id': msgid,
                'timestamp': timestr
            })
        
        if batch:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for item in batch:
                    future = executor.submit(deletemsg, item['channel_id'], item['message_id'])
                    futures.append((future, item))
                for future, item in futures:
                    if future.result():
                        deleted += 1
                        if deleted % 10 == 0 or deleted == 1:
                            print(f"deleted [{deleted}] voice message ({item['timestamp']})")
            
            time.sleep(0.1)
        offset += 25
    return deleted

def processmessages(channelid, userid):
    deleted = 0
    offset = 0
    while True:
        result = searchmessages(channelid, userid, offset)
        if not result:
            break
        messages = result.get('messages', [])
        if not messages:
            break
        batch = []
        
        for msggroup in messages:
            if isinstance(msggroup, list) and len(msggroup) > 0:
                msg = msggroup[0]
            else:
                continue
            channelid_msg = msg.get('channel_id')
            msgid = msg.get('id')
            timestamp = msg.get('timestamp', '')
            
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestr = dt.strftime('%Y-%m-%d %H:%M')
                except:
                    timestr = timestamp[:10]
            else:
                timestr = "unknown"
            
            batch.append({
                'channel_id': channelid_msg,
                'message_id': msgid,
                'timestamp': timestr
            })
        
        if batch:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for item in batch:
                    future = executor.submit(deletemsg, item['channel_id'], item['message_id'])
                    futures.append((future, item))
                for future, item in futures:
                    if future.result():
                        deleted += 1
                        if deleted % 10 == 0 or deleted == 1:
                            print(f"deleted [{deleted}] message ({item['timestamp']})")

            time.sleep(0.1)
        offset += 25
    return deleted

def main():
    try:
        userinfo = getuserinfo()
        userid = userinfo['id']
        username = userinfo['username']
        print(f"logged in as {username}")
        resolvedtarget = resolvetarget(target_id)
        if not resolvedtarget:
            print("target not found (use a guild id, a user id for DM, or a DM channel id)")
            return
        
        channelid = resolvedtarget['channel_id']
        targetname = resolvedtarget['target_name']
        
        print(f"target: {targetname}")
        print("starting deletion process...")
        print("-" * 60)
        totaldeleted = 0

        if delete_config['images'] or delete_config['videos'] or delete_config['audio']:
            print("\nprocessing media files...")
            deleted = processfiles(channelid, userid)
            totaldeleted += deleted
            print(f"deleted {deleted} media files")
        
        if delete_config['voice']:
            print("\nprocessing voice messages...")
            deleted = processvoice(channelid, userid)
            totaldeleted += deleted
            print(f"deleted {deleted} voice messages")
        
        if delete_config['messages']:
            print("\nprocessing text messages...")
            deleted = processmessages(channelid, userid)
            totaldeleted += deleted
            print(f"deleted {deleted} text messages")
        
        print("-" * 60)
        print(f"finished, total deleted: {totaldeleted}")
    except KeyboardInterrupt:
        print("\nstopped by user")
    except Exception as e:
        print(f"error: {str(e)}")

if __name__ == "__main__":
    main()
