from __future__ import print_function
import av
from clarifai_system import NSFWDetector
import base64
from cStringIO import StringIO


def make_prediction(filename):

    """
    Analyzes keyframes in mp4 file.
    Returns the average NSFW score of the video
    :param filename: 'str', /path/to/mp4 file
    :return: <Dict> final_status  {'nsfw': <float>, 'sfw':<float>}
    """
    if type(filename) is unicode:
        filename = filename.encode('ascii', 'ignore')

    container = av.open(filename)
    clarifai_bot = NSFWDetector().Detector

    scores = []

    for frame in container.decode(video=0):
        if frame.key_frame:
            PIL_img = frame.to_image()  # convert pyAV frame to PIL Image

            # convert PIL Image to base64 for Clarifai API
            output = StringIO()
            PIL_img.save(output, format='jpeg')
            b64_img = base64.b64encode(output.getvalue())

            response = clarifai_bot.predict_by_base64(base64_bytes=b64_img)
            predictions = response['outputs'][0]['data']['concepts']

            status = {}
            for i in range(2):
                status.update({predictions[i]['name']:predictions[i]['value']*100})
            scores.append(status['nsfw'])

    avg_nsfw_score = sum(scores)/len(scores) # average across key-frames
    avg_sfw_score = 100 - avg_nsfw_score

    final_status = {'nsfw':avg_nsfw_score, 'sfw':avg_sfw_score}
    return final_status

