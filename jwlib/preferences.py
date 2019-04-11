import ast

global PreferenceTypes
PreferenceTypes = [ "Simulation", "Analysis" ]

def PreferencesError(KeyError):
    def __init__(self, msg):
        KeyError.__init__(self, msg)

def PreferencesFormatError(ValueError):
    def __init__(self, msg):
        ValueError.__init__(self, msg)

class Section:
    def __init__(self, data={}):
        self.__data = data
        
    def CreateEntry(self, key, value):
        self.__data[key] = value
    def GetKeys(self):
        return self.__data.keys()
    def GetEntry(self, key):
        return self.__data[key]
    def HasEntry(self, key):
        return key in self.__data.keys()
    def EntryIsType(self, key, typenm):
        return type(self.__data[key]) is typenm

    def __str__(self):
        return str(self.__data)
    
class Preferences:
    def __init__(self, preftype="free"):
        self.__data = {}
        self.__pref_type = preftype
        
    def CreateSection(self, name):
        self.__data[name] = {}

    def GetEntry(self, section, name):
        return self.__data[section][name]
    def GetSection(self, name):
        if self.HasSection(name):
            return Section(self.__data[name])
        else:
            return Section()
    def HasSection(self, name):
        return name in self.__data.keys()
    def EntryIsType(self, section, key, typenm):
        return type(self.__data[section][key]) is typenm
    
    def SetEntry(self, section, name, value):
        if not section in self.__data.keys():
            raise PreferencesError("Cannot create entry in uninitialized section '%s'." % section)
        self.__data[section][name] = value

    def GetPreferencesType(self):
        return self.__pref_type

    @staticmethod
    def LoadPrefFile(fname):
        f = open(fname, 'r')
        contents = f.read()
        f.close()
        p = None
        sect = ''
        preftype = ''
        lines = contents.split('\n')
        for _i in xrange(0, len(lines)):
            if _i > 0 and p == None:
                raise PreferencesFormatError("Did not find type declaration on the first line.")
            i = lines[_i].lstrip()
            # Comment Line
            if i.startswith('#') or i=='':
                continue
            elif i.startswith('@'):
                if _i != 0:
                    raise PreferencesFormatError("File type must be defined on the first line.")
                else:
                    ftype = i[1:]
                    p = Preferences(ftype)
                    
            # Section Start
            elif i.startswith('.'):
                i = i[1:]
                if not i.isalnum():
                    raise PreferencesFormatError("Invalid section start: '%s'." % ('.' + i))
                elif p.HasSection(i):
                    raise PreferencesFormatError("Invalid duplicate section start for section '%s'." % i)
                else:
                    p.CreateSection(i)
                    sect = i
            elif '=' in i:
                s = i.split('=')
                key = s[0]
                try:
                    value = ast.literal_eval('='.join(s[1:]))
                except:
                    # in case of a bad literal
                    value = None
                if sect == '':
                    raise PreferencesFormatError("Cannot define preferences before defining a section.")
                elif p.GetSection(sect).HasEntry(key):
                    raise PreferencesFormatError("Invalid duplicate preference definition for preference key '%s'." % key)
                else:
                    p.SetEntry(sect, key, value)
            else:
                raise PreferencesFormatError("Invalid line type: %s" % i)
        if p == None:
            p = Preferences("empty")
        return p

    def GenerateFile(self):
        lines = ["@" + self.__pref_type]
        for i in self.__data.keys():
            lines.append('.%s' % i)
            for j in self.__data[i].keys():
                lines.append('%s=%s' % (j, self.__data[i][j]))
        return '\n'.join(lines)
                
