######################################################################
####### Calls the Clarifai Moderation API.############################
####### Their system is not so great, but it flags gore, #############
####### which TheHive.ai's API isn't able to.#########################
######################################################################


from __future__ import print_function
from clarifai.rest import ClarifaiApp
from clarifai.rest import client
import os


class Bot:

    def __init__(self):
        CLARIFAI_API_KEY = os.environ.get("CLARIFAI_API_KEY")
        app = ClarifaiApp(api_key=CLARIFAI_API_KEY)
        self.Detector = app.models.get(model_id='d16f390eb32cad478c7ae150069bd2c6')

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
    link = 'https://i.pinimg.com/736x/69/6e/ca/696ecaa640bad3a0a8b5fbb4398f3b51--medical-pictures-medical-problems.jpg'
    #print (bot.get_predictions(['http://imgur.com/JlVKy4W.jpg']))
    print (bot.get_prediction(link, 'url'))