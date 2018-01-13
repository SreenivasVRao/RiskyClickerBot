from gfycat.client import GfycatClient
from gfycat.error import GfycatClientError
import urllib, os, operator
import VideoBot

class Bot:

    def __init__(self, videobot):
        self.bot = GfycatClient()
        self.video_bot = videobot

    def analyze_gfy(self, link):

        gfyName = link[link.find('.com/')+5:]


        if gfyName.find('.') != -1: #name.mp4
            gfyName = gfyName[:gfyName.find('.')]

        if gfyName.find('-') != -1: #name-someformat.mp4
            gfyName = gfyName[:gfyName.find('-')]

        status = {}
        message = None
        try:
            gfycat_response = self.bot.query_gfy(gfyName)
            mp4_URL = gfycat_response['gfyItem']['mp4Url']

            if gfycat_response['gfyItem']['nsfw']==1:
                message = 'Gfycat - marked NSFW.'
                message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.
            else:
                filename = mp4_URL[mp4_URL.find('.com/') + 5:]
                urllib.urlretrieve(mp4_URL, filename)
                status[link] = self.video_bot.make_prediction(filename)

                labels = sorted(status[link].items(), key=operator.itemgetter(1), reverse=True)
                tag, confidence = labels[0]
                message = tag +". I'm {0:.2f}% confident.".format(confidence)
                message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.

                if os.path.exists(filename):
                    os.remove(filename)

        except GfycatClientError as e:
            print(e.error_message)
            print(e.status_code)

        return status, message




if __name__ == '__main__':
    import SlaveBot
    slave = SlaveBot.Slave()
    video_bot = VideoBot.Bot(slave)
    bot = Bot(video_bot)

    print(bot.analyze_gfy('gfycat.com/ClumsyCaringCassowary'))