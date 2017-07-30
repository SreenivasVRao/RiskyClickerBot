from __future__ import print_function
import praw, json, re
from imgurpython import ImgurClient
from imgurpython.helpers import error
import NSFWDetector
import os
import bmemcached
import pickle
from praw.exceptions import APIException
import argparse

global imgurbot, redditbot, message, heroku


def imgur_init():

    IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID")
    IMGUR_CLIENT_SECRET = os.environ.get("IMGUR_CLIENT_SECRET")
    client = ImgurClient(IMGUR_CLIENT_ID, IMGUR_CLIENT_SECRET)
    return client


def redditbot_init():

    PRAW_CLIENT_ID = os.environ.get('PRAW_CLIENT_ID')
    PRAW_CLIENT_SECRET = os.environ.get('PRAW_CLIENT_SECRET')
    PRAW_PASSWORD = os.environ.get('PRAW_PASSWORD')
    PRAW_USERNAME = os.environ.get('PRAW_USERNAME')
    PRAW_USERAGENT = os.environ.get('PRAW_USERAGENT')

    bot = praw.Reddit(client_id=PRAW_CLIENT_ID,
                      client_secret=PRAW_CLIENT_SECRET, password=PRAW_PASSWORD,
                      user_agent=PRAW_USERAGENT, username=PRAW_USERNAME)
    return bot


def url_analyzer(link):
    # Assuming that the URL is from imgur for now.
    if link.lower().find('imgur.com/') != -1:

        if link.lower().find('/a/') != -1:
            return 'album'

        elif link.lower().find('/gallery/') != -1 :
            return 'gallery'

        else: #will be imgur.com/<image id>, or imgur.com/<image id>.extension
            return 'imgur_image'

    elif link.split('.')[-1].lower() in ['jpeg', 'jpg', 'bmp', 'tiff', 'png']:
        return 'image_direct'

    else:
        return None


def parse_comment(reddit_comment, root=False):

    global redditbot
    bot_reply = None
    with open('blacklist.json', 'rb') as f:
        blacklist = json.load(f)

    sub = reddit_comment.permalink().split('/')[2]
    subreddit = redditbot.subreddit(sub)

    if sub not in blacklist['disallowed'] and not subreddit.over18:
        # not checking NSFW subreddits because that's dumb
        if not root:
            data = reddit_comment.body
        elif root:
            data = reddit_comment.url
        regexp = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+[#0-9A-Za-z]+'
        urls = re.findall(regexp, data)
        # Mainly based on https://stackoverflow.com/a/6883094

        indices = []
        insert_text = []
        current_idx = 0
        next = 0

        failures = 0
        for each_url in urls[0:6]:

            link_type = url_analyzer(each_url)

            result, bot_msg = handle_link(each_url, link_type)
            total = 0

            if result is not None:
                for k, v in result.items():
                    total += result[k]['sfw']
                average = total * 100 / len(result.items())
                insert_text.append(' **{0:.2f}% SFW** '.format(average))

            elif result is None and link_type is None:
                failures += 1
                insert_text.append(' **(Could not process this link.)** ')

            next = data[current_idx:].find(each_url) + len(each_url) + len(data[0:current_idx])
            if next < len(data) and data[next] == ')':
                #accounting for reddit markup
                next += 1

            indices.append(next)
            current_idx = next

        current_idx = 0
        bot_reply = ''
        if len(urls) > failures:
            # i.e., bot was able to process at least one of the urls
            for (idx, txt) in zip(indices, insert_text):
                bot_reply += data[current_idx:idx] + txt
                current_idx = idx
            bot_reply += data[current_idx:]
            #Add the remaining text.

            bottom_text = '\n \n ___ \n \n ^^Am ^^I ^^broken? [^^Contact ^^the ^^Developer](/u/PigsDogsAndSheep)'+ \
                          ' ^^| [^^Source ^^Code](https://github.com/SreenivasVRao/RiskyClickerBot)'+ \
                          '\n \n ^^If ^^I ^^analyzed ^^your ^^parent ^^comment ^^already, ' + \
                          '^^I ^^won\'t ^^reply ^^to ^^you. ^^I ^^also ^^won\'t ^^process ^^more ^^than ^^6 ^^URLS '+ \
                          '^^per ^^parent ^^due ^^to ^^API ^^restrictions.'

            bot_reply = '>' + bot_reply + bottom_text

        else:
            bot_reply = None

    return bot_reply


def handle_link(link, linktype):
    global imgurbot, message
    status = None
    message = None

    if linktype == 'album':
        # will be format imgur.com/a/<album_id> or imgur.com/a/<album_id>#<image_id>
        temp = link.split('/')[-1]
        if '#' in temp:
            # this means an image was linked from an album. Only process that image then.
            image_id = temp[temp.find('#')+1:]
            new_url = 'http://imgur.com/'+image_id
            status, message = handle_link(new_url, 'imgur_image')
        else:
            # user linked to an album
            album_id = temp

            try:
                images_list = imgurbot.get_album_images(album_id)
                links = [item.link for item in images_list[0:10] if 'image/' in item.type]
                # Ensures only images are processed in case there are gifs and images in the album
                # Ensures only 10 images are processed in case album is very large.

                if len(links) > 0:
                    status = NSFWDetector.get_predictions(links)
                    message = '(Processed only ' + str(len(links))+' images from this album.)'
                else:
                    message = '(Album contained no images to process.)'

            except error.ImgurClientError as e:
                message = 'Not able to fetch the album.'
                print (e.error_message)

    elif linktype == 'gallery':
        item_id = link.split('/')[-1]
        # user linked to either an album or an image from the imgur gallery.
        # assume it is album. if it's a 404, assume it is an image.
        if '#' in item_id:
            # i.e., link was imgur.com/gallery/<albumid>#<imageid>
            # user linked to image in album from gallery.

            image_id = item_id[item_id.find('#')+1:]

            try:
                image = imgurbot.get_image(image_id)
                status, message = handle_link(image.link, 'imgur_image')
            except error.ImgurClientError as e:
                print (e.error_message)
                status = None

        elif '#' not in item_id:
            try:
                album = imgurbot.get_album(album_id=item_id)

                status, message = handle_link(album.link, 'album')

            except error.ImgurClientError as e:
                try:
                    image = imgurbot.get_image(item_id)

                    status, message = handle_link(image.link, 'imgur_image')

                except error.ImgurClientError as e:
                    print (e.error_message)
                    message = 'Broken Link.'

    elif linktype == 'imgur_image':
        link = ensure_extension(link)
        status = NSFWDetector.get_predictions([link])

    elif linktype == 'image_direct':
        status = NSFWDetector.get_predictions([link])

    elif linktype is None:
        status = None
        message = "(Couldn't process this link.)"

    return status, message


def ensure_extension(link):
    global imgurbot
    temp = link.split('/')[-1]  # will be <image_id>.<extension> or <image_id>
    if '.' not in temp:
        image_id = temp
        link = imgurbot.get_image(image_id).link
        return link
    else:
        return link


def get_comment(new_comment, new_parent):
    id = None
    if not new_comment.is_root:
        botreply = parse_comment(new_parent)

    elif new_comment.is_root:
        submission = redditbot.submission(new_parent)
        botreply = parse_comment(submission, root=True)

    try:
        if botreply is not None:
            new_comment.reply(botreply)
            id = new_parent.id
    except APIException as a:
        print(a.message, a.error_type)

    return id


def main():
    global redditbot, location

    mc = None #will be memcache client if running app from heroku
    posts_replied_to = []
    mc_keys = []
    if not heroku and os.path.exists("posts_replied_to.p"):
        # Read local file into a list and remove any empty values
        with open("posts_replied_to.p", "rb") as f:
            posts_replied_to = pickle.load(f)
            posts_replied_to = list(filter(None, posts_replied_to))

    elif heroku:
        MEMCACHEDCLOUD_SERVERS = os.environ.get('MEMCACHEDCLOUD_SERVERS')
        MEMCACHEDCLOUD_USERNAME = os.environ.get('MEMCACHEDCLOUD_USERNAME')
        MEMCACHEDCLOUD_PASSWORD = os.environ.get('MEMCACHEDCLOUD_PASSWORD')

        mc = bmemcached.Client((MEMCACHEDCLOUD_SERVERS,), MEMCACHEDCLOUD_USERNAME,
                               MEMCACHEDCLOUD_PASSWORD)

    subreddit = redditbot.subreddit('all')

    for n, comment in enumerate(subreddit.stream.comments()):
        if 'risky click' in comment.body.lower():
            parent = comment.parent()
            parse = ((not heroku) and (parent.id not in posts_replied_to)) \
                or (heroku and (mc.get(parent.id) is None))
            if parse:
                id = get_comment(new_comment=comment, new_parent=parent)
                if id is not None:
                    if heroku:
                        mc.set(parent.id, 'T')
                    else:
                        posts_replied_to.append(parent.id)

        elif n % 5000 == 0:
            # Check inbox for mentions every 5000 comments.
            mail = redditbot.inbox
            summons = mail.mentions(limit=30)
            for each in summons:
                if each.new:
                    comment = redditbot.comment(id=each.id)
                    parent = comment.parent()
                    parse = ((not heroku) and (parent.id not in posts_replied_to)) \
                            or (heroku and (mc.get(parent.id) is None))
                    # Parse parent if it's local, and parent comment already not replied to.
                    # Or parse if it's on heroku, and parent comment is not in memcache

                    if parse:
                        id = get_comment(new_comment=comment, new_parent=parent)
                        if id is not None:
                            if heroku:
                                mc.set(each, 'T')
                            else:
                                posts_replied_to.append(parent.id)

                    each.mark_read()
                else:
                    break
        print (n)
    if not heroku:
        with open("posts_replied_to.p", "wb") as f:
            pickle.dump(posts_replied_to, f)

    # running this bot locally is not a great idea because
    # it will never exit the subreddit comment stream
    # so your list will grow huge and never get saved
    # granted, it's just a few characters at a time. But just saying.
    # It's 1:10 AM, and I want to release this bot into the wild.
    # So.

    print ("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--heroku', action='store_true')
    arguments = parser.parse_args()
    heroku = arguments.heroku
    imgurbot = imgur_init()
    redditbot= redditbot_init()
    main()
