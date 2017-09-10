from __future__ import print_function
from clarifai.rest import ClarifaiApp
from clarifai.rest import client
import os


class NSFWDetector:

    def __init__(self):
        CLARIFAI_API_KEY = os.environ.get("CLARIFAI_API_KEY")
        app = ClarifaiApp(api_key=CLARIFAI_API_KEY)
        self.Detector = app.models.get(model_id='e9576d86d2004ed1a38ba0cf39ecb4b1')

    def get_predictions(self, link_list):
        probabilities = {}

        for link in link_list:
            try:
                reply = self.Detector.predict_by_url(url=link)

                results = reply['outputs'][0]['data']['concepts']
                temp = {link: {results[0]['name']: results[0]['value']*100,
                               results[1]['name']: results[1]['value']*100}}
                probabilities.update(temp)
            except client.ApiError as e:
                print ('Clarifai', e.error_desc)
                continue

        return probabilities


if __name__ == '__main__':
    ClarifaiBot = NSFWDetector()
    answer = ClarifaiBot.Detector.predict_by_url('http://imgur.com/JlVKy4W.jpg')
    print (type(answer))
    print (answer['outputs'][0]['data']['concepts'])