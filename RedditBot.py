from __future__ import print_function
import json, re, os, operator, urllib, argparse

import praw
from praw.exceptions import APIException
import prawcore
import ImgurBot
import VideoBot
import bmemcached
import SlaveBot
import GfycatBot
import moviepy.editor as mp

class RiskyClickerBot:

    def __init__(self, heroku, slave_bot, imgurbot, videobot, gfycatbot):

        PRAW_CLIENT_ID = os.environ.get('PRAW_CLIENT_ID')
        PRAW_CLIENT_SECRET = os.environ.get('PRAW_CLIENT_SECRET')
        PRAW_PASSWORD = os.environ.get('PRAW_PASSWORD')
        PRAW_USERNAME = os.environ.get('PRAW_USERNAME')
        PRAW_USERAGENT = os.environ.get('PRAW_USERAGENT')

        self.bot = praw.Reddit(client_id=PRAW_CLIENT_ID,
                          client_secret=PRAW_CLIENT_SECRET, password=PRAW_PASSWORD,
                          user_agent=PRAW_USERAGENT, username=PRAW_USERNAME)
        self.markupregex = re.compile("( )*http.+\)", re.S)
        self.newlineregex = re.compile("\n\n")
        self.heroku_flag = heroku
        self.slave_bot = slave
        self.imgurbot = imgurbot
        self.video_bot = videobot
        self.gfycat_bot = gfycatbot

    def url_analyzer(self, link):
        # Assuming that the URL is from imgur for now.
        if 'imgur.com/' in link.lower():

            if '/a/' in link.lower():
                return 'imgur_album'

            elif '/gallery/' in link.lower():
                return 'imgur_gallery'

            elif link.split('.')[-1].lower() in ['gif', 'gifv', 'mp4','webm']:
                # will be imgur.com/<image id>, or imgur.com/<image id>.extension
                # handle gif, gifv, mp4
                return 'imgur_video'

            else:
                # will be imgur.com/<image id>, or imgur.com/<image id>.extension
                # prevents gif, gifv, mp4 from being parsed
                return 'imgur_image'

        elif link.split('.')[-1].lower() in ['jpeg', 'jpg', 'bmp', 'tiff', 'png']:
            return 'image_direct'

        elif link.split('.')[-1].lower() in ['gif', 'gifv', 'webm']:
            return 'gif'

        elif link.split('.')[-1].lower() in ['mp4']:
            return 'mp4'

        elif 'gfycat.com/' in link.lower():
            return 'gfycat_video'

        # elif 'media.giphy.com/' in link.lower():
        #     return 'giphy_gif'
        #

        else:
            return None

    def get_markup_offset(self, text):
        x = re.search(self.markupregex, text)

        if x is not None:
            return x.endpos
        else:
            return 0

    def parse_comment(self, reddit_comment, root=False):

        bot_reply = None
        with open('blacklist.json', 'rb') as f:
            blacklist = json.load(f)
            sub = reddit_comment.permalink.split('/')[2].lower()

        subreddit = self.bot.subreddit(sub)

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
                link_type = self.url_analyzer(each_url)

                if link_type is None:
                    failures += 1
                    insert_text.append(' **(Could not process this link.)** ')

                else:
                    result, bot_msg = self.handle_link(each_url, link_type)
                    if bot_msg is not None:
                        insert_text.append(' '+bot_msg)
                    elif bot_msg is None:
                        failures += 1
                        insert_text.append(' **(Could not process this link.)** ')

                    url_start_idx = data[current_idx:].find(each_url)

                    next = len(data[0:current_idx]) + url_start_idx + len(each_url)

                    # next += self.get_markup_offset(data[url_start_idx:])
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

                bottom_text = '\n \n ___' + \
                              '\n\n^^*RiskyClickerBot* ^^*v2*' + \
                              ' ^^| [^^Summon ^^me!](http://imgur.com/TsvwFht)' + \
                              ' ^^| [^^Source ^^Code](https://github.com/SreenivasVRao/RiskyClickerBot)' + \
                              ' ^^| [^^How ^^it ^^works](https://medium.com/@sreenivasvrao/introducing-u-riskyclickerbot-22b3d56d1e2a)' + \
                              ' ^^| ^^Made ^^by ^^/u/PigsDogsAndSheep!'

                bot_reply = self.handle_multiline_comment(bot_reply)
                bot_reply += bottom_text

            else:
                bot_reply = None

        return bot_reply

    def handle_multiline_comment(self, text):
        matches_iterator = re.finditer(self.newlineregex, text)

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

    def handle_link(self, link, linktype):
        status = None
        message = None
        if linktype == 'imgur_album':
            status, message = self.imgurbot.handle_album(link)

        elif linktype == 'imgur_gallery':
            status, message = self.imgurbot.handle_gallery(link)

        elif linktype == 'imgur_image':
            status, message = self.imgurbot.handle_images([link])

        elif linktype == 'imgur_video':
            status, message = self.imgurbot.handle_videos([link])

        elif linktype == 'image_direct':
            status = self.slave_bot.analyze([link])

            if status[link] is not None:
                labels = sorted(status[link].items(), key=operator.itemgetter(1), reverse=True)

                tag, confidence = labels[0]

                message = tag + ". I'm  {0:.2f}% confident.".format(confidence)

                if tag is 'SFW':
                    manning_distance = self.slave_bot.clarifai_bot.match_template(link, 'manning')
                    if manning_distance is not None and manning_distance <= 0.01:
                        message += ' Might be Manning Face.'

                message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.

            else:
                status = None
                message = None

        elif linktype is 'gif' or linktype is 'mp4':
            filename = 'video.mp4'

            if linktype is 'gif':
                urllib.urlretrieve(link, 'test.gif')
                clip = mp.VideoFileClip("test.gif")
                clip.write_videofile(filename)
                if os.path.exists('test.gif'):
                    os.remove('test.gif')

            elif linktype is 'mp4':
                urllib.urlretrieve(link, filename)

            status = {link: self.video_bot.make_prediction(filename)}

            if status[link] is not None:
                labels = sorted(status[link].items(), key=operator.itemgetter(1), reverse=True)

                tag, confidence = labels[0]

                message = tag + ". I'm  {0:.2f}% confident.".format(confidence)
                message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.
            else:
                status = None
                message = None

            if os.path.exists(filename):
                os.remove(filename)

        elif linktype == 'gfycat_video':
            status, message = self.gfycat_bot.analyze_gfy(link)


        elif linktype is None:
            status = None
            message = None

        return status, message

    def generate_comment(self, new_comment, new_parent, test=True):
        id = None
        botreply = ''
        if not new_comment.is_root:
            botreply = self.parse_comment(new_parent)

        elif new_comment.is_root:
            submission = self.bot.submission(new_parent)
            botreply = self.parse_comment(submission, root=True)

        try:
            if botreply is not None:
                if not test:
                    new_comment.reply(botreply)
                    id = new_parent.id
                    print ('I made a new comment: reddit.com'+ new_comment.permalink)
                else:
                    print (botreply)

        except APIException as a:
            print(a.message, a.error_type)
        except prawcore.exceptions.Forbidden as e:
            print (e.message) # If bot is banned from the sub.

        return id

    def check_mentions(self, memcache):

        mail = self.bot.inbox
        summons = mail.mentions(limit=30)
        for each in summons:
            if each.new:
                each.mark_read()
                comment = self.bot.comment(id=each.id)
                parent = comment.parent()
                parse = (memcache.get(parent.id) is None) and (parent.author != 'RiskyClickerBot')
                # parse if not in cache
                # parse if bot is not author
                if parse:
                    id = self.generate_comment(new_comment=comment, new_parent=parent)
                    if id is not None:
                        memcache.set(id, 'T')

            else:
                break

        return memcache

    def get_memcache_client(self):
        # Store IDs of comments that the bot has already replied to.
        # Read local cache by default

        MEMCACHEDCLOUD_SERVERS = '127.0.0.1:11211'
        MEMCACHEDCLOUD_USERNAME = 'user'
        MEMCACHEDCLOUD_PASSWORD = 'password'

        if self.heroku_flag:
            MEMCACHEDCLOUD_SERVERS = os.environ.get('MEMCACHEDCLOUD_SERVERS')
            MEMCACHEDCLOUD_USERNAME = os.environ.get('MEMCACHEDCLOUD_USERNAME')
            MEMCACHEDCLOUD_PASSWORD = os.environ.get('MEMCACHEDCLOUD_PASSWORD')

        client = bmemcached.Client((MEMCACHEDCLOUD_SERVERS,), MEMCACHEDCLOUD_USERNAME,
                               MEMCACHEDCLOUD_PASSWORD)
        return client

    def browseReddit(self):

        memcache_client = self.get_memcache_client()

        subreddit = self.bot.subreddit('all')

        for n, comment in enumerate(subreddit.stream.comments()):
            if 'risky click' in comment.body.lower() or 'r/riskyclick' in comment.body.lower() \
                    or 'riskyclick' in comment.body.lower():
                print ('Permalink is', comment.permalink)
                parent = comment.parent()
                parse = (memcache_client.get(parent.id) is None) and (parent.author != 'RiskyClickerBot')

                # If the parent is not already replied to
                # and if the parent comment is not by this bot

                if parse:
                    id = self.generate_comment(new_comment=comment, new_parent=parent, test=False)
                    if id is not None:
                        memcache_client.set(parent.id, 'T')
                else:
                    print (parent.author, memcache_client.get(parent.id))

            elif n % 5000 == 0:
                print (n)

                memcache_client = self.check_mentions(memcache_client)
                # Check inbox for mentions every 5000 comments.

        # running this bot locally is no longer a bad idea

        memcache_client.disconnect_all()

        # disconnect from server once done.

        print ("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--heroku', action='store_true')
    arguments = parser.parse_args()
    heroku = arguments.heroku

    slave = SlaveBot.Slave()
    VideoBot= VideoBot.Bot(slave)
    imgurbot = ImgurBot.Bot(VideoBot, slave)

    GfyBot = GfycatBot.Bot(VideoBot)
    RiskyClickerBot = RiskyClickerBot(heroku, slave, imgurbot, VideoBot, GfyBot)
    comment = RiskyClickerBot.bot.comment(id='dtg8fmg')
    parent = comment.parent()
    RiskyClickerBot.generate_comment(comment, parent)

    #RiskyClickerBot.browseReddit()
