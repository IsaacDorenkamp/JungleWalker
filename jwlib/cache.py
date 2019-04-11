# Model Cache

import glob
import gzip
import json
import os

class ModelCache:
    def __init__(self, directory='cache'):
        if len(glob.glob(directory)) == 0:
            os.mkdir(directory)
        self.__cachedir = directory
    def Store(self, model_id, model_content):
        with gzip.open(self.__cachedir + '/' + str(model_id) + '.cc', 'wb') as gzf:
            gzf.write(model_content)
    def Get(self, model_id):
        if len(glob.glob(self.__cachedir + '/' + str(model_id) + '.cc')) == 0:
            return None
        content = ""
        with gzip.open(self.__cachedir + '/' + str(model_id) + '.cc', 'rb') as gzf:
            content = gzf.read()
        return json.loads(content)
