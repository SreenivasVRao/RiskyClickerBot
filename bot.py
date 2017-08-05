from __future__ import print_function
import praw, json, re
from imgurpython import ImgurClient
from imgurpython.helpers import error
import NSFWDetector
import os
import bmemcached
import time
from praw.exceptions import APIException
import argparse

global imgurbot, redditbot, message, heroku

markupregex = re.compile("( )*http.+\)", re.S)
newlineregex = re.compile("\n\n")


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
    if 'imgur.com/' in link.lower():

        if '/a/' in link.lower():
            return 'album'

        elif '/gallery/' in link.lower():
            return 'gallery'

        elif link.split('.')[-1].lower() not in ['gif', 'gifv', 'mp4','webm']:
            # will be imgur.com/<image id>, or imgur.com/<image id>.extension
            # prevents gif, gifv, mp4 from being parsed
            return 'imgur_image'

    elif link.split('.')[-1].lower() in ['jpeg', 'jpg', 'bmp', 'tiff', 'png']:
        return 'image_direct'

    else:
        return None


def get_markup_offset(text):
    x = re.search(markupregex, text)

    if x is not None:
        return x.endpos
    else:
        return 0


def parse_comment(reddit_comment, root=False):

    global redditbot
    bot_reply = None
    with open('blacklist.json', 'rb') as f:
        blacklist = json.load(f)
    if root:
        sub = reddit_comment.permalink.split('/')[2].lower()
    else:
        sub = reddit_comment.permalink().split('/')[2].lower()
    # Bleddy PRAW has a weird kink. Submission objects have permalink as an attribute
    # Comments have permalink as a function

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

            sfwtotal = 0
            nsfwtotal = 0

            if result is not None:
                for k, v in result.items():
                    sfwtotal += result[k]['sfw']
                    nsfwtotal += result[k]['nsfw']
                if len(result.items()) > 0:
                    sfwaverage = sfwtotal * 100 / len(result.items())
                    nsfwaverage = nsfwtotal * 100 / len(result.items())

                    if sfwaverage > nsfwaverage:
                        insert_text.append(" **SFW (I'm {0:.2f}% confident)** ".format(sfwaverage))
                        print ('SFW', sfwaverage)
                    else:
                        insert_text.append(" **NSFW (I'm {0:.2f}% confident)** ".format(nsfwaverage))
                        print ('NSFW', nsfwaverage)

            elif result is None:
                failures += 1
                insert_text.append(' **(Could not process this link.)** ')

            url_start_idx = data[current_idx:].find(each_url)

            next = len(data[0:current_idx]) + url_start_idx + len(each_url)

            next += get_markup_offset(data[url_start_idx:])
            # if next < len(data) and data[next] == ')':
            #     #accounting for reddit markup
            #     next += 1

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

            bottom_text = '\n \n ___' + \
                          '\n\n^^*RiskyClickerBot* ^^*v1.1*' + \
                          '\n\n ^^Am ^^I ^^broken? [^^Contact ^^the ^^Developer](/u/PigsDogsAndSheep)' + \
                          ' ^^| [^^Source ^^Code](https://github.com/SreenivasVRao/RiskyClickerBot)' + \
                          ' ^^| [^^How ^^it ^^works](https://medium.com/@sreenivasvrao/introducing-u-riskyclickerbot-22b3d56d1e2a)' + \
                          ' ^^| [^^More ^^Technical ^^Explanation](https://medium.com/@sreenivasvrao/making-reddit-safer-for-work-with-u-riskyclickerbot-3bcb54fc1fe6)' + \
                          '\n\n ^^You ^^can ^^summon ^^me ^^too. [^^Example](http://imgur.com/TsvwFht) ' + \
                          '\n\n ^^I ^^reply ^^once ^^per ^^parent ^^comment. ^^I ^^also ^^won\'t ^^process ^^more ^^than ^^6 ^^URLS ' + \
                          '^^per ^^parent ^^due ^^to ^^API ^^restrictions.'

            bot_reply = handle_multiline_comment(bot_reply)
            bot_reply = bot_reply + bottom_text

        else:
            bot_reply = None

    return bot_reply


def handle_multiline_comment(text):
    matches_iterator = re.finditer(newlineregex, text)

    fragments = []
    prev = 0

    for n, m in enumerate(matches_iterator):
        fragments.append('>' + text[prev:m.start()])
        prev = m.end()

    fragments.append('>' + text[prev:])  # leftover text
    result = '>'
    for f in fragments:
        result += '\n\n' + f

    return result


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
        if link.split('.')[-1].lower() not in ['gif', 'gifv', 'mp4', 'webm']:
            status = NSFWDetector.get_predictions([link])
        else:
            status = None
            message = " (Couldn't process this link.) "

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


def generate_bot_comment(new_comment, new_parent):
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
            print ('I made a new comment: reddit.com'+ new_comment.permalink())
    except APIException as a:
        print(a.message, a.error_type)

    return id


def check_mentions(memcache):
    global redditbot
    mail = redditbot.inbox
    summons = mail.mentions(limit=30)
    for each in summons:
        if each.new:
            comment = redditbot.comment(id=each.id)
            parent = comment.parent()
            parse = (memcache.get(parent.id) is None) and (parent.author != 'RiskyClickerBot')
            # parse if not in cache
            # parse if bot is not author
            if parse:
                id = generate_bot_comment(new_comment=comment, new_parent=parent)
                if id is not None:
                    memcache.set(id, 'T')

            each.mark_read()
        else:
            break

    return memcache


def get_memcache_client(herokuFlag=False):
    # Store IDs of comments that the bot has already replied to.
    # Read local cache by default

    MEMCACHEDCLOUD_SERVERS = '127.0.0.1:11211'
    MEMCACHEDCLOUD_USERNAME = 'user'
    MEMCACHEDCLOUD_PASSWORD = 'password'

    if heroku:
        MEMCACHEDCLOUD_SERVERS = os.environ.get('MEMCACHEDCLOUD_SERVERS')
        MEMCACHEDCLOUD_USERNAME = os.environ.get('MEMCACHEDCLOUD_USERNAME')
        MEMCACHEDCLOUD_PASSWORD = os.environ.get('MEMCACHEDCLOUD_PASSWORD')

    client = bmemcached.Client((MEMCACHEDCLOUD_SERVERS,), MEMCACHEDCLOUD_USERNAME,
                           MEMCACHEDCLOUD_PASSWORD)
    return client


def main():
    global redditbot

    mc = get_memcache_client(heroku)

    # heroku is a flag - set to True if running from that platform

    # subreddit = redditbot.subreddit('all')
    subreddit = redditbot.subreddit('all')

    for n, comment in enumerate(subreddit.stream.comments()):
        if 'risky click' in comment.body.lower() or 'r/riskyclick' in comment.body.lower():
            print ('Permalink is', comment.permalink())
            parent = comment.parent()
            parse = (mc.get(parent.id) is None) and (parent.author != 'RiskyClickerBot')

            # If the parent is not already replied to
            # and if the parent comment is not by this bot

            if parse:
                id = generate_bot_comment(new_comment=comment, new_parent=parent)
                if id is not None:
                    mc.set(parent.id, 'T')
            else:
                print (parent.author, mc.get(parent.id))

        elif n % 5000 == 0:
            mc = check_mentions(mc)
            # Check inbox for mentions every 5000 comments.
        print (n)


    # running this bot locally is no longer a bad idea

    mc.disconnect_all()

    #disconnect from server once done.

    print ("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--heroku', action='store_true')
    arguments = parser.parse_args()
    heroku = arguments.heroku
    imgurbot = imgur_init()
    redditbot= redditbot_init()
    main()

