import requests
import cache
import json

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
    def __init__(self, reqheaders={}):
        self.__headers = reqheaders
        self.__cache = cache.ModelCache()

    def apireq(self, path, **qparams):
        return api_get_request(path, self.__headers, **qparams)

    def GetAvailableModels(self):
        return self.apireq('model/get')

    def GetModel(self, model_id, mhash, mversion=1, force_refresh=False):
        if not force_refresh:
            cmodel = self.__cache.Get(model_id)
            if cmodel != None:
                return cmodel
        kw = {'version': mversion}
        kw[mhash] = ''
        resp = self.apireq('model/get/%d' % model_id, **kw)['%d/%d' % (model_id, mversion)]
        self.__cache.Store(model_id, json.dumps(resp))
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
