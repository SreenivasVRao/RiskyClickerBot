##########################################################
# Calls theHive.ai Moderation API.                      ##
# Their system is pretty good, but it fails at gore,    ##
# which Clarifai's API will catch.                      ##
##########################################################


import os
import requests



class Bot:

    def __init__(self):
        self.HIVE_API_KEY = os.environ.get('HIVE_API_KEY')

    def get_all_predictions(self, link_list):
        # returns a dictionary key=URL, value = dictionary
        # value = {'class label': probability (0 to 100%)}
        results = {}

        for link in link_list:
            class_labels = self.get_prediction(link, 'url')
            results.update({link: class_labels})

        return results

    def get_prediction(self, img, filetype):

        try:
            headers = {'Authorization': 'Token ' + self.HIVE_API_KEY}
            if filetype is 'url':

                form = {'image_url': img}
                reply = requests.post('https://api.thehive.ai/api/v1/tag/task',
                                      headers=headers, data=form).json()

            elif filetype is 'jpeg':
                with open(img, 'rb') as f:
                    form = {'image': f}
                    reply = requests.post('https://api.thehive.ai/api/v1/tag/task',
                                          headers=headers, files=form).json()
            else:
                print('Invalid Image Type')
                return None
            predictions = reply['status']['response']['output'][0]['classes']

        except:
            print ('Hive.ai API failure')
            return None



        output = {}
        for each in predictions:
            output[each['class']] = each['score']*100


        output['SFW'] = output.pop('clean')
        output['NSFW'] = output.pop('nsfw')
        output['Violent'] = output.pop('violent')
        output['Suggestive'] = output.pop('suggestive')


        return output


if __name__ == '__main__':
    bot = Bot()
    link = 'https://i.pinimg.com/736x/69/6e/ca/696ecaa640bad3a0a8b5fbb4398f3b51--medical-pictures-medical-problems.jpg'
    #print (bot.get_prediction(['http://imgur.com/JlVKy4W.jpg']))
    print (bot.get_prediction(link, 'url'))

