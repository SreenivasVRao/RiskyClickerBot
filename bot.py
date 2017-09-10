from __future__ import print_function
import praw, json, re
import imgur
import clarifai_system
import os
import bmemcached
import VideoAnalyzer
import urllib
from praw.exceptions import APIException
import argparse

global heroku


class RiskyClickerBot:

    def __init__(self):

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

        elif link.split('.')[-1].lower() in ['gif', 'gifv', 'mp4', 'webm']:
            return 'gif'

        # Future work
        # elif 'gfycat.com/' in link.lower():
        #     return 'gfycat_video'
        #
        # elif 'media.giphy.com/' in link.lower():
        #     return 'giphy_gif'
        #
        # elif 'streamable.com/' in link.lower():
        #     return 'streamable_video'

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
        if root:
            sub = reddit_comment.permalink.split('/')[2].lower()
        else:
            sub = reddit_comment.permalink().split('/')[2].lower()
        # Bleddy PRAW has a weird kink. Submission objects have permalink as an attribute
        # Comments have permalink as a function

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
                result, bot_msg = self.handle_link(each_url, link_type)

                if bot_msg is not None:
                    insert_text.append(' '+bot_msg)

                elif result is None:
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
                              '\n\n^^*RiskyClickerBot* ^^*v1.2* ^^| ^^*Now* ^^*with* ^^*experimental* ^^*imgur* ^^*gif* ^^*support!*' + \
                              '\n\n ^^Am ^^I ^^broken? [^^Contact ^^the ^^Developer](/u/PigsDogsAndSheep)' + \
                              ' ^^| [^^Source ^^Code](https://github.com/SreenivasVRao/RiskyClickerBot)' + \
                              ' ^^| [^^How ^^it ^^works](https://medium.com/@sreenivasvrao/introducing-u-riskyclickerbot-22b3d56d1e2a)' + \
                              ' ^^| [^^More ^^Technical ^^Explanation](https://medium.com/@sreenivasvrao/making-reddit-safer-for-work-with-u-riskyclickerbot-3bcb54fc1fe6)' + \
                              '\n\n ^^You ^^can ^^summon ^^me ^^too! [^^Example](http://imgur.com/TsvwFht) ' + \
                              '\n\n ^^I ^^reply ^^once ^^per ^^parent ^^comment. ^^I ^^also ^^won\'t ^^process ^^more ^^than ^^6 ^^URLS ' + \
                              '^^per ^^parent ^^due ^^to ^^API ^^restrictions.'

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

        imgurbot = imgur.Bot()

        if linktype == 'imgur_album':
            status, message = imgurbot.handle_album(link)

        elif linktype == 'imgur_gallery':
            status, message = imgurbot.handle_gallery(link)

        elif linktype == 'imgur_image':
            status, message = imgurbot.handle_images([link])

        elif linktype == 'imgur_video':
            status, message = imgurbot.handle_videos([link])

        elif linktype == 'image_direct':
            status = clarifai_system.NSFWDetector().get_predictions([link])
            # status will be {<link>: {'sfw':<score>, 'nsfw':<score>}

            nsfw_score = status[status.keys()[0]]['nsfw']
            sfw_score = status[status.keys()[0]]['sfw']
            if sfw_score > nsfw_score:
                message = 'SFW. I\'m {0:.2f}% confident'.format(sfw_score)
            else:
                message = 'NSFW. I\'m {0:.2f}% confident'.format(nsfw_score)

        elif linktype == 'gif':
            pass
            #future work

        elif linktype is None:
            status = None
            message = "(Couldn't process this link.)"

        return status, message

    def generate_comment(self, new_comment, new_parent):
        id = None
        botreply = ''
        if not new_comment.is_root:
            botreply = self.parse_comment(new_parent)

        elif new_comment.is_root:
            submission = self.bot.submission(new_parent)
            botreply = self.parse_comment(submission, root=True)

        try:
            if botreply is not None:
                new_comment.reply(botreply)
                id = new_parent.id
                print ('I made a new comment: reddit.com'+ new_comment.permalink())
        except APIException as a:
            print(a.message, a.error_type)

        return id

    def check_mentions(self, memcache):

        mail = self.bot.inbox
        summons = mail.mentions(limit=30)
        for each in summons:
            if each.new:
                comment = self.bot.comment(id=each.id)
                parent = comment.parent()
                parse = (memcache.get(parent.id) is None) and (parent.author != 'RiskyClickerBot')
                # parse if not in cache
                # parse if bot is not author
                if parse:
                    id = self.generate_comment(new_comment=comment, new_parent=parent)
                    if id is not None:
                        memcache.set(id, 'T')

                each.mark_read()
            else:
                break

        return memcache

    def get_memcache_client(self, herokuFlag=False):
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

    def browseReddit(self):

        mc = self.get_memcache_client(heroku)

        # heroku is a flag - set to True if running from that platform

        # subreddit = redditbot.subreddit('all')
        subreddit = self.bot.subreddit('all')

        for n, comment in enumerate(subreddit.stream.comments()):
            if 'risky click' in comment.body.lower() or 'r/riskyclick' in comment.body.lower():
                print ('Permalink is', comment.permalink())
                parent = comment.parent()
                parse = (mc.get(parent.id) is None) and (parent.author != 'RiskyClickerBot')

                # If the parent is not already replied to
                # and if the parent comment is not by this bot

                if parse:
                    id = self.generate_comment(new_comment=comment, new_parent=parent)
                    if id is not None:
                        mc.set(parent.id, 'T')
                else:
                    print (parent.author, mc.get(parent.id))

            elif n % 5000 == 0:
                mc = self.check_mentions(mc)
                # Check inbox for mentions every 5000 comments.
            print (n)

        # running this bot locally is no longer a bad idea

        mc.disconnect_all()

        # disconnect from server once done.

        print ("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--heroku', action='store_true')
    arguments = parser.parse_args()
    heroku = arguments.heroku
    imgurbot = imgur.Bot()
    RiskyClickerBot = RiskyClickerBot()
    comment = RiskyClickerBot.bot.comment(id='dmswooh')
    parent = comment.parent()

    #RiskyClickerBot.generate_comment(comment, parent)
    RiskyClickerBot.browseReddit()
