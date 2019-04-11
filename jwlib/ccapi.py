import datetime
from dateutil.tz import tzlocal
import cache
import json
import pytz
import requests

def do_eq(param):
    param = str(param)
    if param != '':
        param = '=' + param
    return param

# api request functions
def api_get_request(path, headerdict, **qparams):
    qpstr = ""
    if len(qparams) > 0:
        params = [ '%s%s' % (i, do_eq(qparams[i])) for i in qparams.keys() ]
        params.sort(key=lambda item: not '=' in item)
        qpstr = '?' + '&'.join( params )
    r = requests.get('https://api.cellcollective.org/%s' % (path + qpstr), headers=headerdict)
    return r.json()

class AuthenticationError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

class CCSession:
    MODEL_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S %Z'
    
    def __init__(self, reqheaders={}):
        self.__headers = reqheaders
        self.__cache = cache.ModelCache()

    def apireq(self, path, **qparams):
        return api_get_request(path, self.__headers, **qparams)

    def GetAvailableModels(self):
        return self.apireq('model/get')

    def GetModel(self, model_id, mhash, updateDate, mversion=1, force_refresh=False):
        if not force_refresh:
            cmodel = self.__cache.Get(model_id)
            if cmodel != None:
                prev_update = datetime.datetime.strptime(cmodel.get('last_updated'), self.MODEL_DATE_FORMAT)
                prev_update = pytz.utc.localize( prev_update )
                prev_update = prev_update.astimezone( tzlocal() )
                if prev_update == None:
                    return cmodel
                else:
                    if updateDate <= prev_update:
                        # cached model is up to date, return it
                        if 'model' in cmodel: # for backwards compatibility
                            return cmodel['model']
                        else:
                            return cmodel # previous version of JungleWalker stored the model directly in a cache.
                        
                    # if we reach this point, it means our cached model is out of date and we need
                    # to fetch the model again and cache it.
                        
        kw = {'version': mversion}
        kw[mhash] = ''
        resp = self.apireq('model/get/%d' % model_id, **kw)['%d/%d' % (model_id, mversion)]
        store_obj = { 'model': resp, 'last_updated': updateDate.astimezone(pytz.utc).strftime(self.MODEL_DATE_FORMAT) }
        self.__cache.Store(model_id, json.dumps(store_obj))
        return resp

class AuthSession(CCSession):
    def __init__(self, xauthtoken):
        CCSession.__init__(self, {'X-AUTH-TOKEN': xauthtoken})
        self.__xauth = xauthtoken

    @staticmethod
    def Create(username, password):
        authdata = {'username': username, 'password': password}
        r = requests.post('https://api.cellcollective.org/login', data=authdata)
        if not 'X-AUTH-TOKEN' in r.headers.keys():
            raise AuthenticationError("Incorrect credentials or internal server error.")
        return AuthSession(r.headers['X-AUTH-TOKEN'])

    def GetProfile(self):
        return self.apireq('user/getProfile')

    def GetXAuthToken(self):
        return self.__xauth
