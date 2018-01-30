from __future__ import print_function
from imgurpython import ImgurClient
from imgurpython.helpers import error
import os, urllib, operator

class Bot:

    def __init__(self,  videobot, slave_bot):
        """
        Initializes the Imgur Bot with credentials stored in environment variables.
        :return: ImgurClient object
        """
        IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID")
        IMGUR_CLIENT_SECRET = os.environ.get("IMGUR_CLIENT_SECRET")
        self.client = ImgurClient(IMGUR_CLIENT_ID, IMGUR_CLIENT_SECRET)
        self.supported_video_formats = ['gif','gifv', 'webm', 'mp4']
        self.slave_bot = slave_bot
        self.video_bot = videobot

    def handle_album(self, album_link):

        """
        handles imgur links of the format: imgur.com/a/<id>, imgur.com/<id>#<img id>
        :type album_link: 'str'
        :rtype message: 'str' - Analysis message from Bot.
        :rtype status: <Dict> - {'nsfw':<float>, 'sfw':<float>}
        """
        temp = album_link.split('/')[-1]
        album_id = temp.split('#')[0]

        message = None
        status = {}

        try:
            album = self.client.get_album(album_id=album_id)

            imgur_flag = album.nsfw


            if imgur_flag:
                message = 'Album marked NSFW on Imgur.'
                message = '**[Hover to reveal](#s "' + message + '")**'  # reddit spoiler tag added.

            elif not imgur_flag:

                images_list = self.client.get_album_images(album_id)

                links = [item.link for item in images_list[0:10]
                         if item.type.split('/')[-1] not in self.supported_video_formats]
                links_videos = [item.link for item in images_list[0:10]
                                if item.type.split('/')[-1] in self.supported_video_formats]
                # Ensures only 10 images/gifs are processed in case album is very large.

                temp1, _ = self.handle_videos(links_videos)
                temp2, _ = self.handle_images(links)

                status.update(temp1)
                status.update(temp2)

                # for all images, if SFW - mark SFW.
                # if any image is not SFW, find out which one.

                max_nsfw= (None, 0)
                min_sfw = (None, 100)
                for k,v in status.items():
                    labels = sorted(status[k].items(), key=operator.itemgetter(1), reverse=True)

                    tag, confidence = labels[0]

                    if tag is 'SFW' and confidence<=min_sfw[1]:
                        min_sfw = labels[0]

                    elif tag is not 'SFW' and confidence>max_nsfw[1]:
                        max_nsfw = labels[0]


                if max_nsfw != (None, 0):
                    message = "Album has "+str(max_nsfw[0])+" image(s). I'm {0:.2f}% confident.".format(max_nsfw[1])

                elif max_nsfw == (None, 0):

                    message = "Album has "+str(min_sfw[0])+" image(s). I'm {0:.2f}% confident.".format(min_sfw[1])


                message = '**[Hover to reveal](#s "'+message+' ")**'  #reddit spoiler tag added.

        except error.ImgurClientError as e:
            status = None
            message = None
            print ('Imgur Error:', e.error_message)

        return status, message

    def handle_images(self, links):
        status = {}
        message = None

        valid_links = [self.ensure_extension(aLink) for aLink in links
                       if aLink.split('.')[-1].lower() not in ['gif', 'gifv', 'mp4', 'webm']]

        status = self.slave_bot.analyze(valid_links)

        if len(valid_links) == 1:
            link = valid_links[0]
            labels = sorted(status[link].items(), key=operator.itemgetter(1), reverse=True)
            tag, confidence = labels[0]
            message = tag + ". I'm  {0:.2f}% confident.".format(confidence)
            if tag is 'SFW':
                manning_distance = self.slave_bot.clarifai_bot.match_template(link, 'manning')
                if manning_distance is not None and manning_distance <= 0.01:
                    message += ' Might be Manning Face.'

            message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.

        return status, message

    def handle_gallery(self, gallery_link):
        item_id = gallery_link.split('/')[-1]
        # user linked to either an album or an image from the imgur gallery.
        # assume it is album. if it's a 404, assume it is an image.

        message = ''
        status = {}

        try:
            album = self.client.get_album(album_id=item_id)

            imgur_flag = album.nsfw

            if imgur_flag:
                status = {}
                message = 'Album marked NSFW on Imgur.'
                message = '**[Hover to reveal](#s "' + message + '")**'  # reddit spoiler tag added.

            elif not imgur_flag:
                status, message = self.handle_album(album.link)

        except error.ImgurClientError as e:
            try:
                image = self.client.get_image(item_id)
                imgur_flag = image.nsfw

                if imgur_flag:
                    message = 'Item marked NSFW on Imgur.'
                    message = '**[Hover to reveal](#s "' + message + '")**'  # reddit spoiler tag added.

                elif not imgur_flag:

                    if image.type.split('/')[-1] in self.supported_video_formats:
                        status, message = self.handle_videos([image.link])
                    else:
                        status, message = self.handle_images([image.link])

            except error.ImgurClientError as e:
                status = None
                message = None
                print('Imgur Error', e.error_message)

        return status, message

    def handle_videos(self, links):
        status = {}
        message = None
        for each_url in links:
            link = self.ensure_extension(each_url)

            # link is now 'imgur.com/id.extension'
            video_id = link.split('/')[-1].split('.')[0]
            filename = video_id+'.mp4'
            mp4_link = 'http://i.imgur.com/'+filename
            urllib.urlretrieve(mp4_link, filename)
            status.update({each_url:self.video_bot.make_prediction(filename)})

            if os.path.exists(filename):
                os.remove(filename)

        if len(links) == 1:
            link = links[0]
            labels = sorted(status[link].items(), key=operator.itemgetter(1), reverse=True)
            tag, confidence = labels[0]
            message = tag + ". I'm  {0:.2f}% confident.".format(confidence)
            message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.

        return status, message

    def ensure_extension(self, url):
        temp = url.split('/')[-1]  # will be <image_id>.<extension> or <image_id>
        if '.' not in temp:
            image_id = temp

            url = self.client.get_image(image_id).link
            return url
        else:
            return url


if __name__ == '__main__':
    bot = Bot()
