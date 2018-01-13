from __future__ import print_function
import av
import base64
from cStringIO import StringIO
import os


class Bot:

    def __init__(self, slave_bot):
        self.slave_bot = slave_bot

    def make_prediction(self, filename):

        """
        Analyzes keyframes in mp4 file.
        Returns the average NSFW score of the video
        :param filename: 'str', /path/to/mp4 file
        :return: <Dict> final_status  {'nsfw': <float>, 'sfw':<float>}
        """
        if type(filename) is unicode:
            filename = filename.encode('ascii', 'ignore')

        container = av.open(filename)

        total_pred_1 = {'SFW': 0, 'NSFW': 0, 'Suggestive': 0, 'Violent': 0}
        total_pred_2 = {'SFW': 0, 'NSFW': 0, 'Suggestive': 0, 'Violent': 0}

        n_key_frames = 0
        for frame in container.decode(video=0):
            if frame.key_frame:
                PIL_img = frame.to_image()  # convert pyAV frame to PIL Image

                # convert PIL Image to base64 for Clarifai API
                output = StringIO()
                PIL_img.save(output, format='jpeg') # saving image to String Buffer in jpeg format
                b64_img = base64.b64encode(output.getvalue()) # converting jpeg to b64

                PIL_img.save('frame.jpeg')
                pred_1, pred_2 = self.slave_bot.analyze_video_frame('frame.jpeg', b64_img)

                for k,v in pred_1.items():
                    total_pred_1[k]+=v

                for k,v in pred_2.items():
                    total_pred_2[k]+=v

                n_key_frames += 1

                if os.path.exists('frame.jpeg'):
                    os.remove('frame.jpeg')


        avg_pred_1 = {}
        avg_pred_2 = {}
        for k,v in total_pred_1.items():
            avg_pred_1[k] = total_pred_1[k]/n_key_frames

        for k,v in total_pred_2.items():
            avg_pred_2[k] = total_pred_2[k]/n_key_frames

        status = self.slave_bot.combine_predictions(avg_pred_1, avg_pred_2)
        return status

if __name__=='__main__':
    import SlaveBot
    slave = SlaveBot.Slave()
    bot = Bot(slave)
    print(bot.make_prediction('/home/sreenivas/sandbox/RiskyClickerBot/test.mp4'))