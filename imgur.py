from __future__ import print_function
from imgurpython import ImgurClient
from imgurpython.helpers import error
import os
from clarifai_system import NSFWDetector
import VideoAnalyzer
import urllib


class Bot:

    def __init__(self):
        """
        Initializes the Imgur Bot with credentials stored in environment variables.
        :return: ImgurClient object
        """
        IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID")
        IMGUR_CLIENT_SECRET = os.environ.get("IMGUR_CLIENT_SECRET")
        self.client = ImgurClient(IMGUR_CLIENT_ID, IMGUR_CLIENT_SECRET)
        self.supported_video_formats = ['gif','gifv', 'webm', 'mp4']

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

            if imgur_flag:
                message = 'Album marked NSFW on Imgur.'
                message = '**[Hover to reveal](#s "' + message + '")**'  # reddit spoiler tag added.

            elif not imgur_flag:
                nsfw_scores = []
                max_nsfw_score_percentage = 0

                if len(status.values()) > 0:
                    for k, v in status.items():
                        nsfw_scores.append(v['nsfw'])
                    max_nsfw_score_percentage = max(nsfw_scores)

                message = ''

                if max_nsfw_score_percentage > 50:
                    message += 'NSFW album. I\'m {0:.2f}% confident.'.format(max_nsfw_score_percentage)

                elif max_nsfw_score_percentage <= 50:
                    message += 'SFW album. I\'m {0:.2f}% confident.'.format(100 - max_nsfw_score_percentage)

                message = '**[Hover to reveal](#s "'+message+' ")**'  #reddit spoiler tag added.

        except error.ImgurClientError as e:
            status = None
            message = None
            print ('Imgur Error:', e.error_message)

        return status, message

    def handle_images(self, links):
        status = {}
        message = None
        for each_url in links:
            link = self.ensure_extension(each_url)
            if link.split('.')[-1].lower() not in ['gif', 'gifv', 'mp4', 'webm']:
                status = NSFWDetector().get_predictions([link])

        if len(links) == 1:
            nsfw_score = [v['nsfw'] for k,v in status.items()][0]
            sfw_score  = [v['sfw'] for k,v in status.items()][0]

            if nsfw_score > sfw_score:
                message = 'NSFW.  I\'m {0:.2f}% confident.'.format(nsfw_score)
                message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.
            else:
                message = 'SFW. I\'m {0:.2f}% confident.'.format(sfw_score)
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
            status.update({each_url: VideoAnalyzer.make_prediction(filename)})
            os.remove(filename)

        if len(links) == 1:
            nsfw_score = [v['nsfw'] for k,v in status.items()][0]
            sfw_score  = [v['sfw'] for k,v in status.items()][0]

            if nsfw_score > sfw_score:
                message = 'NSFW.  I\'m {0:.2f}% confident.'.format(nsfw_score)
                message = '**[Hover to reveal](#s "' + message + ' ")**'  # reddit spoiler tag added.
            else:
                message = 'SFW. I\'m {0:.2f}% confident.'.format(sfw_score)
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

