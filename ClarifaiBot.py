######################################################################
####### Calls the Clarifai Moderation API.############################
####### Their system is not so great, but it flags gore, #############
####### which TheHive.ai's API isn't able to.#########################
######################################################################


from __future__ import print_function
from clarifai.rest import ClarifaiApp
from clarifai.rest import client
import os
import numpy as np
from scipy import spatial

class Bot:

    def __init__(self):
        CLARIFAI_API_KEY = os.environ.get("CLARIFAI_API_KEY")
        app = ClarifaiApp(api_key=CLARIFAI_API_KEY)
        self.Detector = app.models.get(model_id='d16f390eb32cad478c7ae150069bd2c6')
        self.Embed_Model = app.models.get('general-v1.3', model_type='embed')

    def match_template(self, link, template='manning'):
        try:
            reply = self.Embed_Model.predict_by_url(url=link)
            embedding = reply['outputs'][0]['data']['embeddings'][0]['vector']
            if template is 'manning':
                manning_template = np.load('embeddings/manning_face_embedding.npy')
                distance = spatial.distance.cosine(embedding, manning_template)
            else:
                distance = 2 #max value returned
        except client.ApiError:
            print('Clarifai API failure')
            return None

        return distance

    def get_all_predictions(self, link_list):
        # returns a dictionary key=URL, value = dictionary
        # value = {'class label': probability (0 to 1)}
        results = {}

        for link in link_list:
                class_labels = self.get_prediction(link, 'url')
                results.update({link: class_labels})

        return results

    def get_prediction(self, img, filetype):
        try:
            if filetype is 'b64':
                reply = self.Detector.predict_by_base64(base64_bytes=img)
            elif filetype is 'url':
                reply = self.Detector.predict_by_url(url=img)
            else:
                print('Invalid Image Type')
                raise KeyError
        except client.ApiError:
            print('Clarifai API failure')
            return None

        results = reply['outputs'][0]['data']['concepts']

        output = {results[0]['name']: results[0]['value'] * 100,
                  results[1]['name']: results[1]['value'] * 100,
                  results[2]['name']: results[2]['value'] * 100,
                  results[3]['name']: results[3]['value'] * 100,
                  results[4]['name']: results[4]['value'] * 100}

        output['SFW'] = output.pop('safe')
        output['NSFW'] = output.pop('explicit')
        output['Suggestive'] = output.pop('suggestive')
        output['Violent'] = output.pop('gore')
        output.pop('drug')  # unnecessary class.

        return output

if __name__ == '__main__':
    bot = Bot()
    link = 'http://i0.kym-cdn.com/photos/images/facebook/001/207/210/b22.jpg'

    print (bot.match_template(link, template='manning'))
    #print (bot.get_prediction(link, 'url'))

