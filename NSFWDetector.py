from __future__ import print_function
from clarifai.rest import ClarifaiApp
import os

global app, model


def get_predictions(link_list):
    global app, model
    probabilities = {}

    for link in link_list:

        reply = model.predict_by_url(url=link)

        results = reply['outputs'][0]['data']['concepts']
        temp = {link: {results[0]['name']: results[0]['value'],
                       results[1]['name']: results[1]['value']}}
        probabilities.update(temp)

    return probabilities


def launch_app():
    CLARIFAI_API_KEY= os.environ.get("CLARIFAI_API_KEY")
    app = ClarifaiApp(api_key=CLARIFAI_API_KEY)
    model = app.models.get(model_id='e9576d86d2004ed1a38ba0cf39ecb4b1')
    return app, model


if __name__ == 'NSFWDetector':
    app, model = launch_app()

elif __name__ == '__main__':
    app= launch_app()

    answer = get_predictions(['http://imgur.com/JlVKy4W.jpg'])
    print (answer)